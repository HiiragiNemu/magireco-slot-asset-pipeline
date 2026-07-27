# 2026-07-27 ac7211 split-native component checkpoint v56

This checkpoint closes the currently resolved ac7211 component inventory. It
does not cross-compose native dimensions, claim a complete event timeline, or
alter any uploaded, approved, frozen-handoff, or quarantined media.

## Exact inventory

The covered set contains 15 fully resolved component or mixed events:

```text
ac7211_001
ac7211_005–015
ac7211_019–021
```

The hash-bound audience catalog contains 53 resolved occurrences and 39 unique
source files. None of those source SHA-256 values overlaps the previous current
material index.

The durable output is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
material_collections_v56_ac7211_split_components_review_20260727
```

It contains three separate, non-upscaled visual-only review products:

- `ac7211_character_sequence_components_416_v1`: 33 native 416x232 sources,
  74.132 seconds, manifest SHA-256
  `CE38CDC763B5DA770AAD7C159D8569A6EE3018983BC65B921F3F7DE33BEE7F5F`,
  output SHA-256
  `765CBE97873138082489845C5E1926DA5B2CFD8C07F0567801A7E0276F754609`;
- `ac7211_event014_components_512x288_v1`: 5 native 512x288 sources,
  10.767 seconds, manifest SHA-256
  `486CDEDF71F7565566209D2C69B6E339EECF08B05B04C68360C20DE9B0B663F2`,
  output SHA-256
  `874281BFE5C58F317C09A8F1F7E378152443FD9545A610D262257CBDCA74B3CB`;
- `ac7211_portrait_standby_component_192x320_v1`: one native 192x320
  source shared by all 15 events, 2.166 seconds, manifest SHA-256
  `17A29939979B5A4F4E13C59F19018E1A16B3F5279596CEDEE8B260146853B2B4`,
  output SHA-256
  `6EF3B9C5F0E749577EEBBEC34C63EFBE3A3D0D4AD16B0B2D6816CBC6642D2CD1`.

Thirty-seven sources have no audio stream. Two sources carry 48 kHz stereo
ALAC tracks whose measured output peak is -91 dB; the formal products drop
those tracks as digital silence. They are not relabeled as dialogue, SE, or
BGM.

## Coverage and exclusions

The coverage audit passes 15/15 events, 53/53 occurrences, 39/39 sources and
zero unused sources:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
material_component_coverage_v56_ac7211_20260727\
ac7211_split_native_components_v1.json
```

SHA-256:
`815894AA77E27FDAD8665DCC4A264A767E33E48D3D4BEFB5C55947CED4DEA86D`.

`ac7211_002–004` and `_016–018` are not resolved by this evidence and remain
explicitly excluded. The three products preserve their native canvas sizes.
No cross-size concatenation, overlay, scale, pad, crop, or natural-session
claim is authorized.

## Review delivery

The three review packages are:

- U137:
  `bilibili_incremental_review_v56_material_native416x232_20260727`;
- U138:
  `bilibili_incremental_review_v56_material_native512x288_20260727`;
- U139:
  `bilibili_incremental_review_v56_material_native192x320_20260727`.

Each package has separate none/JA/ZH target names backed by same-volume
hardlinks to one canonical silent visual file. Each exact file remains
human-playback-required; all three roots have zero `UPLOAD_NOW` media and zero
quarantine media. Package-summary SHA-256 values are:

```text
U137  7549D6312150F8DA5CFDD4EE2CD4F549007D6223C70204A6A6B5A26DF618E1FA
U138  ABF2056B4C73223E8659971CAF8B6D0D86FD0465664FD9F29349077BF1FD6AC7
U139  4DF121303B4645A9595C3FC6D65F6541021BD54C51060DB5FA8B27AB5A110CD2
```

## Ledger and upload guide

`production_ledger_v24_20260727` is current:

- produced audience events: 195;
- material-covered audience events: 618;
- produced DirInfo routes: 79;
- child-local timing blockers: 330;
- quarantined audience events: 53.

Its `SUMMARY.json` SHA-256 is
`2C8C5CBE992DB3CFC3CE27EEF0B2BF6C1A2B7E3559FB3300997ECDCE6DBFA8FC`.

`upload_guide_v56_20260727` contains 10 already-uploaded exact files, 17 exact
files currently allowed for upload, 314 human-playback-required files and
8 explicit exclusions, 341 indexed exact files total. Its JSON SHA-256 is
`7EEA8B980CB19991FA6D53CEC02A8C2CC906F55CE1E0628452D8B85F50453EFB`.

P16/ac6003, P17/ac6004 and P18/ac6005 remain hard-quarantined. Formal with-BGM
candidates remain zero.

Final repository regression: `python -m unittest` — 473 passed, 4 skipped.
