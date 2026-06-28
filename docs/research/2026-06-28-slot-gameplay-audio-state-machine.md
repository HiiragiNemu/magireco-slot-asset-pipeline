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

Machine-readable summary tables were generated with:

```text
tools/frida_runtime_probe/summarize_runtime_audio_capture.py
```

Output:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_gameplay_input_probe_20260628\summary_tables
```

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

## Larger-chunk recapture

`csl_audio_queue_probe.js` was adjusted from a 2 MiB per-chunk cap to an 8 MiB
per-chunk cap while keeping the total dump cap at 96 MiB.  This prevents
gameplay BGM/effect chunks from being silently metadata-only during focused
diagnostics.

Recapture output:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_gameplay_input_probe_large_chunk_20260628
```

Decoded listening artifact:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_gameplay_input_probe_large_chunk_20260628\slot_gameplay_large_chunk_runtime_audio_timeline.wav
```

Summary table output:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_gameplay_input_probe_large_chunk_20260628\summary_tables
```

Evidence skeleton output:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_gameplay_input_probe_large_chunk_20260628\evidence_skeleton_v1
```

This later run took a different random/gameplay branch: it loaded
`ac0908_001`, `ac0908_002`, `ac0909_*`, and reel UI resources instead of the
earlier `ac0910` branch.  It produced 25 fully dumped queue chunks and no
metadata-only chunks:

```json
{
  "chunk_count": 25,
  "source_total_pcm_bytes": 11216610,
  "duration_seconds": 19.862375,
  "observed_sound_ids": [60, 61, 64, 291, 864, 1768, 6698, 6709, 8573, 8575, 9002],
  "largest_dumped_chunk_bytes": 2949132
}
```

The recapture proves the larger cap works.  It did not reproduce the earlier
`814` / sound id `287` branch, so that specific branch still needs targeted
state steering if its audio is needed for final evidence.

The first run also has an evidence skeleton:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_gameplay_input_probe_20260628\evidence_skeleton_v1
```

That skeleton is intentionally marked evidence-only and carries the
metadata-only warning for `814` / sound id `287`.

## Targeted `814` / sound id `287` recapture

A later focused slot-input capture reused the 8 MiB per-chunk cap and sent 8
lever/stop cycles from the visible slot UI:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_targeted_814_probe_20260628
```

Decoded listening artifact:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_targeted_814_probe_20260628\slot_targeted_814_runtime_audio_timeline.wav
```

Summary and evidence skeleton:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_targeted_814_probe_20260628\summary_tables
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_targeted_814_probe_20260628\evidence_skeleton_v1
```

Packaged evidence:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_targeted_814_probe_20260628\evidence_package_v1
```

The package was generated with
`tools/frida_runtime_probe/package_runtime_evidence_capture.py` and includes
`source_hashes.csv`, `cumulative_runtime_timeline.csv`, `qa_report.json`, and
`package_manifest.json`.

Result:

```json
{
  "chunk_count": 47,
  "duration_seconds": 41.395020833333334,
  "observed_sound_ids": [60, 61, 62, 64, 278, 279, 287, 291, 445, 451, 453, 531, 1769, 2993, 3196, 3198, 3206, 6698, 6714, 6758, 6759, 6760, 9002],
  "metadata_sound_ids": []
}
```

Evidence package QA:

```json
{
  "status": "passed_evidence_not_delivery",
  "timeline_rows": 128,
  "hashed_files": 12,
  "queue_metadata_count": 0,
  "rendered_rms_dbfs": -21.187805792199768
}
```

The previously capped branch is now resolved:

| Runtime evidence | Static mapping |
| --- | --- |
| active event `ac0910_001` at about 28.249 s requested sound code `814` | request table id `344`, SMZ `213B22458D11890FF6BEEC183F22.smz` |
| final OpenSL queue chunk at about 28.309 s had `sound_id_u16_at_0x2=287`, `buffer_bytes=3072004`, not metadata-only | `sound_id.dat` maps OGG chunk `287` to `snd_00814_bank01_ogg_00287.ogg` |

This confirms the runtime path and removes the earlier evidence gap for this
gameplay sound.  It does not authorize a clean-story render because the capture
is a slot gameplay state-machine sequence with reel/UI state.

As a negative gate check, the original first slot capture was also packaged:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_gameplay_input_probe_20260628\evidence_package_v1
```

That package reports `failed_evidence_package` because it still has
`queue_metadata_count=1` and the skeleton warning
`capture contains metadata-only queue chunks; recapture with larger per-chunk cap before delivery`.
This is the intended behavior: incomplete audio evidence must not enter the
render/long-form pipeline.

Both packages are indexed by:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\runtime_evidence_package_audit_20260628
```

Current index summary:

```json
{
  "package_count": 2,
  "status_counts": {
    "failed_evidence_package": 1,
    "passed_evidence_not_delivery": 1
  },
  "failed_check_counts": {
    "no_metadata_only_queue_chunks": 1,
    "skeleton_has_no_warnings": 1
  }
}
```

The package index is then converted into a conservative promotion/isolation
queue:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\runtime_evidence_promotion_queue_20260628
```

Current queue summary:

```json
{
  "package_count": 2,
  "promotion_lane_counts": {
    "blocked_failed_runtime_evidence_package": 1,
    "runtime_gameplay_or_slot_material_with_dialogue_audio": 1
  },
  "clean_story_status_counts": {
    "not_eligible": 1,
    "not_eligible_gameplay_or_slot_sequence": 1
  }
}
```

The passed `814/287` package is therefore retained as reliable runtime audio
evidence but isolated from clean-story/Bilibili rendering.  Its next action is
material/gameplay review only.

The runtime evidence queue is also copied into the global strategy report:

```text
A:\magireco_corrected_research_20260612\pipeline_strategy_audits_v18_runtime_evidence_gate_20260628
```

This report keeps the v18 production/coverage counts unchanged while adding
package-level runtime evidence status:

```json
{
  "runtime_evidence_package_count": 2,
  "runtime_evidence_status_counts": {
    "failed_evidence_package": 1,
    "passed_evidence_not_delivery": 1
  },
  "runtime_evidence_promotion_lane_counts": {
    "blocked_failed_runtime_evidence_package": 1,
    "runtime_gameplay_or_slot_material_with_dialogue_audio": 1
  },
  "runtime_evidence_clean_story_status_counts": {
    "not_eligible": 1,
    "not_eligible_gameplay_or_slot_sequence": 1
  }
}
```

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

- extend the evidence skeleton into a strict production-manifest builder only
  after each scene has complete visual, subtitle, and final OpenSL/game-decoder
  audio evidence;
- continue reversing `zgSndWinDllConstruction -> zgSndInit -> SndSystem::init`
  only as a separate official-decoder route;
- use `slot_gameplay_runtime_audio_timeline.wav` for human listening checks.

Forbidden next actions:

- promoting forced single-event `ac0921_001` as complete;
- producing new clean-story or Bilibili uploads from contact sheets only;
- using numeric `ac` suffixes or sound-code numbers as direct CRI/OGG indices;
- merging gameplay UI, slot foregrounds, or gold-frame/particle effects into
  normal animation editions.
