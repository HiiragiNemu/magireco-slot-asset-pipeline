# Human progress report - MagiaReco slot animation recovery

Date: 2026-07-04

This is the short human-facing state report after the second A: RAM-disk loss.
The project goal is unchanged: produce auditable, native-resolution animation
archives and Bilibili-facing same-scene long editions with correct image,
voice, subtitles, BGM/bed, and SE.  Slot/gold/particle/gameplay material must be
kept separate from normal story animation.

## Current safety state

- Authoritative repository:
  `C:\Users\cryne\.codex\worktrees\7454\com.universal777.magireco-Ga9DaxEd9F9Lqn9OVKVSfw==`
- Authoritative branch: `codex/corrected-runtime-pipeline`
- Durable evidence/progress root: `D:\magia\MyProducts\casino`
- A: was lost again and was not restored.  Treat A: only as disposable scratch.
  Do not rely on any A:-only file for handoff, QA, or final delivery decisions.
- MuMu/ADB recovered after the second outage:
  `emulator-5554`, game PID `4207`, physical resolution `2160x3840`,
  Frida ports `27042` and `27043` forwarded.

## What is already solid progress

1. The project is no longer using the bad v18 visual/contact-sheet strategy.
   Those outputs are invalidated because they can have wrong BGM, wrong voice,
   wrong subtitles, or wrong visual state even when the MP4 stream is technically
   playable.

2. The repository and working branch are corrected:
   all current work is on `codex/corrected-runtime-pipeline`, not accidental
   `main`.

3. Several earlier user-accepted families exist and remain valuable inputs:
   `ac1102` family, `ac1103` family, `ac1104` family, and the food/restaurant
   sample.  They still need the newer strict AV/BGM/timeline gate before final
   long-edition publication.

4. For `ac7114_001`, `ac7115_001`, and `ac7116_001`, the v19 clean audio-gate
   outputs have user-confirmed correct voice/subtitle alignment.  They are not
   yet final Bilibili long-edition proof because the natural outer-flow BGM/bed
   question remains open.

5. The `ac7116_001` tail-frame hold is no longer just a renderer guess.  Z2D
   movie-layer / CRI receiver evidence shows the game can keep the movie at its
   final decoded frame while voice/subtitle timing continues.  The same route
   has also been extended to `ac7114_001` and `ac7115_001`.

6. The downstream story-lottery route is now mapped:

   ```text
   fnRxComDirInfo3 callback payload[6]=8
     -> SdGmData+0x130 -> +0x0a8 -> +0x184 -> +0x358
     -> SdGmData+0x13be=16
     -> story kind/character lottery
   ```

7. The upstream command-buffer route is now partially mapped:

   ```text
   LC701A_SLOT staging/queue
     -> ID401::getCmdBuf(dst, 0xc00)
     -> CSlotBody::analysPacket() 8-byte packet loop
     -> ID401::accessSubProcess(packet)
     -> byte-reversed callback payload
     -> fnRxComDirInfo3
   ```

   Because `ID401::accessSubProcess()` reverses the 8 raw bytes before callback
   dispatch, the upstream raw packet condition for the proved route is:

   ```text
   packet_id == 19
   raw_packet[1] == 8
   ```

8. After the second outage, a real complete physical-input spin was captured
   with lightweight observer + ADB taps.  The run reached real slot state
   transitions (`bet=0..3`, `credit=50..47`, state/mode `1/2/3`) and had no
   hook/parse errors.  It observed ordinary BGM helper calls and final audio
   queue chunks (`sound_id=9002` and `sound_id=60`), proving outer slot sound
   machinery is active in natural play.

9. A reusable parser was added:
   `tools/frida_runtime_probe/summarize_lightweight_spin_probe.py`.  It turns
   lightweight runtime JSONL into auditable JSON/CSV packet, RxCom, lottery,
   BGM, queue, event-code, and slot-state summaries.

## What the latest full-spin run proved

Latest durable evidence:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_id401_cmd_buffer_full_spin_adb_continuation_20260704
```

Generated parser output:

```text
summary_lightweight_spin_probe_v2.json
summary_lightweight_spin_probe_v2_packets.csv
summary_lightweight_spin_probe_v2_rxcom.csv
summary_lightweight_spin_probe_v2_lottery.csv
summary_lightweight_spin_probe_v2_bgm.csv
summary_lightweight_spin_probe_v2_queue.csv
summary_lightweight_spin_probe_v2_event_codes.csv
summary_lightweight_spin_probe_v2_play_start.csv
```

Important numbers from the parser:

- observer JSONL size: 6,232,052 bytes
- packet observations: 9,660, including staging repeats
- unique raw packet forms: 35
- target story-dispatch candidates: 0
- DirInfo3 packet observations: 768
- RxCom rows: 6
- lottery rows: 10
- BGM helper rows: 162
- final audio queue rows: 2
- hook errors: 0
- parse errors: 0

The complete command buffer included the natural ordinary DirInfo3 packet:

```text
[19, 0, 8, 0, 0, 1, 1, 29]
```

This is not the target packet.  Its `8` is at raw byte 2, not raw byte 1.  After
the ID401 byte reversal, that becomes callback payload byte 5, not payload byte
6, so it does not feed the proved `SdGmData+0x358=8` story-dispatch route.

## Distance to the final target

This is not ready for full Bilibili publication yet.

The strongest current estimate is:

- Infrastructure/recovery/probing base: mostly in place.
- ac7114/ac7115/ac7116 visual-tail + voice/subtitle correctness: mostly solved,
  with BGM/outer-flow still open.
- General mechanism for all scenes: partially solved.  The downstream
  story-dispatch path is proved, but the upstream LC701A producer condition is
  not yet decoded.
- Full Bilibili long-edition production: not yet safe to mass-run.  Rendering
  before the AV/BGM mechanism is closed risks generating more technically
  playable but wrong videos.

Practical interpretation: the project is past the "random manual guessing"
stage, but not yet at the "scale all scenes and upload" stage.  The remaining
hard work is mechanism closure and AV trust, not ffmpeg rendering.

## What is still missing

1. Natural condition for target story dispatch:
   find the game state / LC701A label / slot-firmware path that emits
   `packet_id=19 && raw_packet[1]=8`.

2. Natural same-run evidence connecting:

   ```text
   LC701A packet candidate
     -> SdGmData story dispatch
     -> SP Story stage/selector
     -> concrete DGM/movie layer
     -> final sound queues
   ```

3. Natural outer-flow BGM/bed proof:
   decide whether target story scenes have no extra BGM, carry an existing slot
   BGM, or request scene-specific bed audio that must be mixed into the final
   render.

4. Re-audit accepted v15 families with the stricter AV gate before making
   final same-scene long editions.

5. Generate final Bilibili-oriented long videos only after the scene/family has:
   source hashes, event index, cumulative timeline, subtitle/no-subtitle
   editions, audio manifest, render manifest, and QA report.

6. Package reproducibility dependencies for Git/GitHub Release without uploading
   inappropriate giant source blobs into Git history.

## Immediate next engineering path

Do not continue one-by-one visual sorting of `ac` folders.  The next useful work
is to decode the generic scheduler:

1. Use `summary_lightweight_spin_probe_v2_packets.csv` to identify LC701A
   staging evolution around DirInfo3.
2. Trace the LC701A producer side that writes `raw_packet[1]`.
3. Capture a natural run where `packet_id=19 && raw_packet[1]=8` appears.
4. In that same run, capture SP Story object state and final OpenSL queue rows.
5. Only then render/promote Bilibili-facing long editions.

