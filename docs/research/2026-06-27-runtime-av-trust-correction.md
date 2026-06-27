# Runtime AV trust correction - 2026-06-27

## Problem confirmed

User review found that the v18 technical render pipeline had promoted outputs
that were not trustworthy as final animation:

- `ac0921_001` has no expected BGM in the rendered output.
- `ac4901_025` and `ac4901_026` contain voice/subtitle cues while the visible
  character does not visibly speak; the family is also a set of very short,
  near-duplicate variants and not a Bilibili-ready long animation by itself.
- `ac7204` material/result outputs contain role voice audio; these are not pure
  silent/material clips and must not be described as such.

The previous QA only proved stream properties, non-silent audio, and
subtitle/no-subtitle audio equality.  It did not prove runtime-complete audio,
BGM/SE/voice coverage, subtitle correctness, or visual speech consistency.

## Invalidated outputs

The following roots are now explicitly invalidated for coverage and delivery in
`tools/frida_runtime_probe/invalidated_output_roots.json`:

```text
A:\magireco_corrected_research_20260612\validation_outputs_v18_generic_strategy_sample_20260626
A:\magireco_corrected_research_20260612\validation_outputs_v18_clean_story_ac4901_full
D:\MagiReco_Reverse\magireco_verified_series_v18_clean_story_ac4901_20260626
A:\magireco_corrected_research_20260612\validation_outputs_v18_clean_story_ac7204_full
A:\magireco_corrected_research_20260612\validation_outputs_v18_clean_story_ac7204_character_subset
D:\MagiReco_Reverse\magireco_verified_series_v18_clean_story_ac7204_character_subset_20260626
```

These files are preserved on disk for audit, but `build_coverage_audit.py` now
ignores them when calculating completed single-event QA, series coverage, or
material coverage.

## Recomputed state

After applying the invalidation list:

```json
{
  "ready_events": 521,
  "ready_with_single_event_QA": 304,
  "ready_missing_single_event_QA": 217,
  "ready_with_series_or_preserved": 267,
  "ready_without_series": 254,
  "excluded_with_material_collection": 82,
  "excluded_without_material_collection": 323,
  "invalidated_output_root_count": 6
}
```

The strategy report now also consumes the runtime AV trust audit and writes:

```text
A:\magireco_corrected_research_20260612\pipeline_strategy_audits_v18_20260626\av_blocked_queue.csv
```

Current AV trust audit status:

```json
{
  "invalidated_do_not_use": 78,
  "blocked_pending_runtime_av_verification": 10
}
```

## Resolver correction

`resolve_official_event_capture.py` now parses more runtime sound evidence:

- string-based `sound_mng_play_bytes` remains the strongest actual playback
  evidence;
- integer playback calls such as `sound_mng_play_request` and
  `sound_mng_wrap_request` only resolve `arg0`, preventing channel/bank
  arguments from becoming false request IDs;
- integer helper calls are de-duplicated when a same-resource string playback is
  present within five milliseconds;
- pure numeric sound requests can fall back from `sound_resource_id` to
  `ogg_chunk_index` using `internal_audit/sound_id_records.csv`.

Smoke test using the existing official runtime capture
`ac7114_001__runtime.jsonl`:

```json
{
  "event": "ac7114_001",
  "video_assets": 5,
  "resolved_videos": 5,
  "sounds": 5,
  "resolved_ogg": 5,
  "subtitles": 3
}
```

Function-level check for the old BGM clue `9078` now resolves:

```text
request_id=2074
ogg=snd_04718_bank03_ogg_09078.ogg
media_mapping_basis=ogg_chunk_index
```

## New promotion rule

No newly rendered event or series can be promoted to Bilibili-ready output from
technical QA alone.  Promotion now requires:

1. runtime-complete audio evidence, including BGM, SE, and voice where the game
   plays them;
2. subtitle evidence from runtime text, verified override, or another auditable
   source, not merely a sound label when visual speech is questionable;
3. visual/speech consistency review for events containing role voice;
4. semantic lane separation: normal animation, gameplay/result with role voice,
   and pure material/effect collections must remain separate.

The next engineering work should prioritize capturing and resolving the missing
runtime sound mechanism for known bad samples (`ac0921_001`, `ac4901_025/026`,
and representative `ac7204` events) before more broad rendering.

## 2026-06-27 follow-up: high-level sound request coverage

Static inspection of `libGameProc.so` showed that the earlier runtime probe only
covered the lower `SoundMng`/Z2D playback surface.  It did not hook the
higher-level slot sound scheduler, including:

- `C_CtrlSndLib::fnReqSndEventCode(uint64_t)`;
- `C_CtrlSndLib::fnReqSndSoundCode(...)`;
- `C_CtrlSndLib::fnReqSndSeqenceSC(...)`;
- `C_CtrlSndLib::fnReqSndSoundCodeCallBack(...)`;
- `SoundMng_play_bySoundCd` / `SndReqBySoundCd`.

This matters for `ac0921_001`: the static event timeline contains only
`259_ボタン音ボイス消音`, `2990_次回予告_レバー`, and the Z2D voice
callbacks.  If the game plays a longer BGM/sequence for the preview scene, it
must be observed at this higher scheduler layer rather than inferred from the
old static event timeline.

`runtime_probe.js` now records these high-level requests.  The resolver now:

- maps high-level sound-code requests to official OGG when the code is present
  in the sound request tables;
- keeps unresolved high-level sound evidence in
  `unresolved_sound_events.csv` and `event_manifest.json`;
- reports `actual_play_sound_count`, `high_level_sound_request_count`, and
  `unresolved_sound_event_count` so incomplete captures cannot masquerade as
  complete AV manifests.

The resolver smoke test on the existing `ac7114_001` capture still resolves the
same five videos, five OGG tracks, and three subtitles, with zero unresolved
new high-level events.

## 2026-06-27 current MuMu capture diagnosis

`diagnose_runtime_capture_state.py` records the current capture surface before
any new runtime event is requested:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\capture_state_20260627
```

Current result:

```json
{
  "verdict": "blocked_x86_frida_cannot_see_arm64_game_code",
  "gadget_127_0_0_1_27043_ok": false,
  "x86_127_0_0_1_27042_ok": true,
  "x86_arch": "x64",
  "x86_sees_libGameProc": false,
  "native_bridge": "libnb.so"
}
```

The app is visible in MuMu, and the x86_64 frida-server can attach to the
process shell, but it only sees the x64/native-bridge surface.  It does not see
the ARM64 game code needed by `event_scene_probe.js` or `runtime_probe.js`.
The ARM64 frida-server still closes the connection under native bridge.  The
existing Java-layer Gadget injector also fails from the x86 attach surface
because Frida reports `Java is not defined`.

Therefore no new `ac0921`, `ac4901`, or `ac7204` runtime capture should be
claimed until the ARM64 Gadget endpoint at `127.0.0.1:27043` is actually
reachable again.  Broad rendering remains paused; the correct next runtime step
is to restore Gadget loading, then re-capture the bad samples with the expanded
high-level sound hooks.

### Realm re-check

The diagnostic was expanded to test all useful Frida attach realms and Java
bridge visibility instead of only the default x86 attach surface:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\capture_state_realm_20260627
```

Current result:

```json
{
  "verdict": "blocked_x86_frida_cannot_see_arm64_game_code",
  "package_primary_abi": "arm64-v8a",
  "ro_debuggable": "0",
  "native_bridge": "libnb.so",
  "default_realm": {
    "ok": true,
    "arch": "x64",
    "hasJava": false,
    "sees_libGameProc": false
  },
  "native_realm": {
    "ok": true,
    "arch": "x64",
    "hasJava": false,
    "sees_libGameProc": false
  },
  "emulated_realm": {
    "ok": false,
    "error": "ProtocolError('process is not using emulation')"
  }
}
```

This rules out a simple `frida --realm emulated` fix for the current MuMu
session.  The default and native realms still attach only to the x64 process
shell; the emulated realm is rejected; and Frida exposes no Java bridge from
this x86 surface.  The capture tools now accept an optional `--realm
native|emulated` for future environments where Frida can expose the correct
surface, but no current capture should be promoted without a reachable ARM64
Gadget or equivalent proof that `libGameProc` hooks are active.

### Gadget recovery

The older successful recovery path was found in the archived 2026-06-18 session:
attach to the x86 frida-server endpoint and run `inject_gadget.js`, which loads
the already-pushed ARM64 Gadget from the app private directory.  This path works
again in the current MuMu session.

Reusable command:

```powershell
python tools\frida_runtime_probe\reinject_gadget.py `
  --out-dir 'A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\gadget_reinject_tool_smoke4_20260627'
```

The recovery evidence is:

```json
{
  "ok": true,
  "pid": "3213",
  "gadget_arch": "arm64",
  "gadget_sees_libGameProc": true
}
```

Follow-up diagnosis:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\capture_state_after_gadget_reinject_v3_20260627
```

Current verdict:

```json
{
  "verdict": "runtime_capture_ready_via_arm64_gadget"
}
```

`title_scene_host.py status` also attached through the Gadget and installed
scene hooks using global `libGameProc` exports, confirming the app is currently
in the slot scene and that the native game probe path is active:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\title_status_after_gadget_reinject_20260627.jsonl
```

Important diagnostic correction: in this native-bridge environment
`Process.enumerateModules()` may report the game mapping as
`split_config.arm64_v8a.apk`.  The reliable proof is resolving a known game
export such as `_ZN8CScnSlot4CalcEv` and then calling
`Process.findModuleByAddress(...)`.  `diagnose_runtime_capture_state.py` and
`reinject_gadget.py` now use that export-based check before declaring the
Gadget capture path ready.

## 2026-06-27 strategy queue protection

`report_pipeline_strategy.py` no longer leaves AV-blocked events in the
actionable render queue.  When a runtime AV trust CSV is supplied:

- `ready_missing_queue.csv` contains only ready-missing events that are not
  `invalidated_do_not_use` or `blocked_pending_runtime_av_verification`;
- `av_blocked_ready_missing_queue.csv` contains the ready-missing events that
  must be repaired or re-captured before any render/series work;
- `verification_sample_queue.csv` samples from the actionable queue, so it does
  not suggest invalidated events for batch rendering.

The recomputed v18 strategy state is:

```json
{
  "ready_missing_single_event_QA": 217,
  "ready_missing_single_event_QA_delivery_actionable": 166,
  "ready_missing_single_event_QA_av_blocked": 51,
  "verification_sample_queue_av_blocked": 0
}
```

The largest AV-blocked ready-missing family is `ac4901` with 36 events; these
are no longer offered as Bilibili/clean-story render candidates.
