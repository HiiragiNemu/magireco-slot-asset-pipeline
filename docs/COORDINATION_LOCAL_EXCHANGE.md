# Local coordination exchange

> ARCHIVED / RETIRED: this is the August 2026 protocol record, not an active instruction. Do not restart its polling, timers, tasks, or peer writes. Current work proceeds in this task under the latest direct user request.

The two active MagiaReco tasks exchange operational status through one durable
local directory instead of repeated task messages:

`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\manifests\coordination_exchange`

- Production task `019f9520-0925-7cb0-b494-ab9282a9a3a7` owns only
  `FROM_019F9520.md`.
- Supervisory/Git integration task `019edabb-004a-7811-889d-8013745c11ac`
  owns only `FROM_019EDABB.md`.
- Each task reads the peer file about every 30 minutes and after an atomic
  checkpoint, then records the peer timestamp it consumed in its own file.
- Updates use a temporary file followed by an atomic replacement. Neither task
  edits the peer-owned file.
- Media, historical roots, and evidence are not moved or deleted by this
  exchange protocol.

The durable directory's `PROTOCOL.md` is authoritative for the live exchange.
