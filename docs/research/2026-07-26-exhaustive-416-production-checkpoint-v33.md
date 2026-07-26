# 2026-07-26 exhaustive 416 production checkpoint v33

## Outcome

This checkpoint keeps P16/ac6003, P17/ac6004, and P18/ac6005 in hard
quarantine while expanding unrelated native 416x232 no-BGM production.
No 512-family expansion or upscale was performed. Codex did not upload media.

The durable production roots are:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  no_bgm_editions_v30_approved_416_routes_20260726
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  no_bgm_editions_v31_mature_416_route_expansion_20260726
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  no_bgm_editions_v32_ac0908_complete_entry_routes_20260726
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  no_bgm_editions_v33_ac4903_mature_routes_20260726
```

Together they hold 47 content products and 141 final none/JA/ZH MP4 files:

| Root | Content products | Final MP4 | Human approval boundary |
|---|---:|---:|---|
| v30 | 9 | 27 | exact ac0908 route/showcase ZH and ac7210 rows 0/1 ZH only |
| v31 | 13 | 39 | exact new outputs still require playback |
| v32 | 6 | 18 | approved source contract; exact new outputs still require playback |
| v33 | 19 | 57 | automated QA only; exact new outputs still require playback |

`no_bgm` means BGM is intentionally excluded while hash-bound verified voice
and scene SE are retained. It does not mean that every unknown sound has been
classified or that a scene is inherently silent.

## v32 ac0908 complete-entry routes

DirInfo kind 33 rows 6–11 are kept as six independent routes:

```text
ac0908_001 → ac0908_002 → ac0908_008
ac0908_001 → ac0908_003 → ac0908_008
ac0908_001 → ac0908_004 → ac0908_008
ac0908_001 → ac0908_005 → ac0908_008
ac0908_001 → ac0908_006 → ac0908_008
ac0908_001 → ac0908_007 → ac0908_008
```

The entry uses exactly the approved 187-frame v28 restaurant exterior and
side-cooking presentation. Its approved scene-audio overlay is allowed to
continue across the outcome boundary. The six products are not concatenated
and are not presented as one native session.

Automated QA confirms native 416x232, 30 fps, H.264/AAC 48 kHz stereo, no
upscale, exact frame/sample grids, exact DirInfo rows, subtitle round-trip,
and sibling-edition packet/decoded-PCM identity.

```text
BATCH_MANIFEST.json
FDD86EE89E0FC6F2DB6A9AD88D6404BF4011B62FFCBC589BE5EACDA89429A1CC

AUTOMATED_QA.json
1F257C92043EEF9307E7567191E3F64F995EBEAADB16C4538A015C0993397533
```

## v33 ac4903 clean routes

DirInfo kind 114 contains 22 rows. This batch produces the 19 rows that do
not terminate in `ac4903_015`:

```text
0–13, 15–17, 19–20
```

Rows 14, 18, and 21 terminate in `ac4903_015`, whose evidence mixes native
416x232 story content with a 256x144 victory/gameplay effect. They remain in
the gameplay/effect layered-composition queue and are not clean-story routes.

The preflight corrected an important evidence error. The simple events
`ac4903_001`, `_007`, `_008`, `_016`, and `_018` are not audio-empty. Each has
one direct-parent scene-SE request at event-global time zero:

| Event | Request | Sound code | Official OGG |
|---|---:|---:|---|
| ac4903_001 | 1709 | 8200 | snd_08200_bank03_ogg_09571.ogg |
| ac4903_007 | 1715 | 8206 | snd_08206_bank03_ogg_09577.ogg |
| ac4903_008 | 1716 | 8207 | snd_08207_bank03_ogg_09578.ogg |
| ac4903_016 | 1715 | 8206 | snd_08206_bank03_ogg_09577.ogg |
| ac4903_018 | 1715 | 8206 | snd_08206_bank03_ogg_09577.ogg |

The OGG files are bound to durable D: paths and SHA-256. Their tails are mixed
on the full route timeline and may continue across the next event boundary.
The already approved P13 ZH source file is untouched.

The 19 routes produce 57 final MP4 files. Automated QA confirms exact DirInfo
coverage, source-family and official-clip hashes, direct-parent SE rows,
cross-boundary SE tails, native media specifications, frame/sample grids,
subtitle round-trip, and none/JA/ZH packet/decoded-PCM identity per route.

```text
BATCH_MANIFEST.json
64BE46ADB85DC7D8B776FF5B6069492411E43AB909F2947F3EBEF628A0720877

AUTOMATED_QA.json
BFB4B0A927754BF69F5303D4BAF802DAA1233653617032BD0DF05450F000210C
```

All 57 exact outputs still require owner playback before publication.

## Exhaustive ledger v2

The authoritative ledger root is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  production_ledger_v2_20260726
```

It consumes only explicitly listed current roots and hash-bound catalogs.
Historical roots are not silently mixed into production inputs. Every current
root requires an explicit `superseded` path exclusion.

Mother-set counts:

| Mother set | Count |
|---|---:|
| Audience events | 7,753 |
| Production-manifest events | 926 |
| DirInfo routes | 13,558 |
| Component/mixed review rows | 5,508 |
| Current production manifests | 22 |
| Superseded audit manifests excluded | 1 |

The current ledger has 172 produced audience events and 51 produced DirInfo
routes. The remainder is assigned to blocked, gameplay/effect collection, or
material collection. P16/P17/P18 quarantine overrides every other state.

The earlier ledger error is closed:

- `v30/ac7210` is the only current ac7210 route root;
- `v30/ac7210_superseded_verbose_audit` is recorded only in
  `SUPERSEDED_AUDIT_INDEX.json`;
- ac7210 rows 0/1 are produced;
- ac7210 rows 2/3/4 are explicit blockers and are not inferred from excluded
  manifest rows;
- ac4903 rows 14/18/21 remain gameplay/effect layered-composition items.

```text
SUMMARY.json
602C8099A81562577BB27CF5B6503E037F21F9BACC2372A15B0280F67F1AC0C7

SHA256SUMS.json
8C0CDB85C5E7829229BB328C00E7F03D2618022B2BB661EE3A7274C1CE5E0C74
```

## Upload guide

Every future production checkpoint must include an upload guide with target
BV/track, absolute folder, exact filename, suggested part title, append or
replace action, automated QA, human approval, and explicit exclusions.

The current guide is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  upload_guide_v33_20260726
```

It contains JSON, CSV, and Markdown views of the same 155 exact files:

- 10 exact ZH files already uploaded by the owner; do not repeat;
- 13 exact files allowed for upload;
- 132 exact files that still require owner playback;
- 6 explicit exclusion scopes.

Of the 13 allowed files, 11 are ZH: P12, P23, six ac0908 strong-entry route
segments, the separately labelled ac0908 reference-derived showcase, and two
ac7210 row 0/1 supplements. The remaining two are the exact owner-approved P12
and P23 JA files for a future JA-track BV. The owner's current story BV number
is not present in local evidence, so the guide labels that target explicitly
rather than inventing a BV identifier.

P16/P17/P18, ac7210 rows 2/3/4, ac4903 rows 14/18/21, and every superseded
audit directory are excluded.

```text
UPLOAD_GUIDE.json
1C9951072EEE457E5F43432CDB804C7C1F15D9D3B0B1A1F9988071A853B1352B

UPLOAD_GUIDE.md
FFD5CB23D1BEB4C35A3B489BCD391045519D71B966A706FA717768AE5B45FD34

UPLOAD_GUIDE.csv
D491ECF3960A49F42B424018196B984489ED1FC82ECCEFADF35C6AD702DD023D
```

## Runtime prerequisite

The runtime prerequisite is the durable record:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260725\
  RUNTIME_RECOVERY_FRIDA_17_16_4.md
```

The Frida 17.5.2 zygote-agent contamination was removed by a complete reboot.
Host Frida, device server, and ARM64 Gadget are unified at 17.16.4; zygote64
and zygote32 were verified clean. Numeric-PID attach on the real slot screen
was validated. Process/application enumeration, spawn, zygote attach,
simultaneous Gadget clients, and broad observers remain prohibited. Any P16
probe must be one lightweight, single-session parent-DGM-to-child-Z2D probe
after reading the current PID through ADB. Local rendering is independent of
that runtime blocker.
