# Native 512 Remaining Materials v45

Date: 2026-07-27

## Result

The durable production root is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  material_collections_v45_native512_remaining_review_20260727
```

Five visual-only products cover all remaining pure native 512x288
production-manifest gameplay/effect events outside ac5102:

| Collection | Events | Clips | Duration | SHA-256 |
| --- | ---: | ---: | ---: | --- |
| `ac3102_roulette_battle_visual_catalog_v1` | 57 | 118 | 215.782 s | `7F232E2F9DC22E909CC9BC68135D8A14B4F9391745315EF68959FD3C26A89614` |
| `ac3103_roulette_color_visual_catalog_v1` | 24 | 32 | 91.528 s | `8C310E30F0D1A632F0C8C38DC70D5EA89E0D71729E4C9E70212F72228A2BADB4` |
| `ac3407_character_reveal_visual_catalog_v1` | 12 | 28 | 9.067 s | `D7DE9A52E2B882028EE6AED68E7E6A23055DFEC61A877A4109DCDDBAADB562BE` |
| `ac3409_character_reveal_visual_catalog_v1` | 12 | 28 | 9.067 s | `F835B1CF1C92D17D0666DC04EA0BF2D0C2F24C59A6733F36C9F24C1E2FE8B4FE` |
| `ac8000_next_story_visual_catalog_v1` | 2 | 4 | 24.000 s | `016F0D19587A0BA3AA00F27C5CE3BC9996B2B4489A71725B5BCCBEC85279150B` |

All five outputs are native 512x288, 30fps, H.264 and have no audio stream.
The video packets are copied directly. No source is resized or upscaled.

## Derived clip-list gate

These catalogs contain 210 distinct official clip names. To avoid a second
hand-maintained source list, the material builder now supports:

```text
derive_clips_from_covered_event_manifests = true
```

For each catalog it:

1. validates the exact event set against the hash-bound v13 production-event
   ledger;
2. rehashes every v20 manifest path and hash named by the ledger;
3. walks events and clips in declared order;
4. derives each official name from the manifest `dgm_name`;
5. resolves that name through the official-name video map;
6. verifies the resolved MP4 has the same exact SHA-256 as the source path
   named by the event manifest;
7. deduplicates repeated official names without dropping event provenance.

The regression fixture covers both ordinary `acNNNN_NNN` names and the
multi-segment `ac6101_2_01` form introduced in v44.

## Audio and subtitle boundary

The 107 covered source events contain 378 audio layers and 150 subtitle cues.
They are deliberately excluded from the five visual-only catalogs. No
child-local timing is consumed or promoted.

The products are gameplay/effect material catalogs. They do not claim:

- a natural game session;
- a clean-story route;
- the original event audio mix;
- resolved dialogue/subtitle timing;
- a route order across mutually exclusive events.

## Incremental review package

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  bilibili_incremental_review_v45_native512_remaining_20260727
```

U086-U090 are in `02_REVIEW_MATERIAL\batch_001`. Each visual-only product has
three correctly named none/JA/ZH hardlink entries. There are 15 target entries,
five unique hashes and ten legal same-inode cross-target aliases. Unique
playback is 349.4431 seconds.

There are zero files in `00_UPLOAD_NOW` and zero quarantined MP4s. Every exact
hash remains on hold until project-owner playback approval.

```text
PACKAGE_SUMMARY.json  A78D067A15FCDFBAB8300AF2F1C75FB7FDD0604E9EA4AD8130EE9FCBB2E63E7F
UPLOAD_INDEX.csv      369FD532C76815193522C687A22CD48696D5D5D41DE37CF53BA351F32EA425F4
SHA256SUMS.txt        25956A6B19B2A05D04BC2C410EF3AB8CD39082ABEF8C51EA9B78A257DAD5083C
```

## Ledger and upload guide

`production_ledger_v14_20260727` advances material coverage from 181 to 288
events and reduces production-manifest `planned_unproduced` from 227 to 120.
The remaining 120 are all ac5102. Blocked timing and quarantine counts remain
unchanged.

```text
SUMMARY.json
  AC96CB656649CE88C26618FEC813CEAEE6C0B9724BAA4A8E0DD3B89AA65CCDE2
CURRENT_MATERIAL_COLLECTION_INDEX.json
  48B0FA17372237D84F4FBAAC0720D28235618C65CEC2D45B553A9F6D787BD1EB
SHA256SUMS.json
  47764159AA74E20E6E516648AF92DC7F32ACCAAF77C32079D2E43D92717AE82F
```

`upload_guide_v45_20260727` contains 10 already-uploaded files, 17 exact
ready-to-upload files, 201 exact files requiring playback and eight explicit
exclusions, for 228 exact files total.

```text
UPLOAD_GUIDE.json  4CA5D539F5054124892D003A27BCAEEF3613B5C618B4661B6544513599324109
UPLOAD_GUIDE.md    AFD261CAFF5716D67A8A4FE8D2949A371FC4DDC0DCA6F2856E11F9A55B4131B9
UPLOAD_GUIDE.csv   B640ADBB64864E11DB2D74BA7B0EAD9B2FA5586ACC20A08065BEBD319700BFCC
SHA256SUMS.json    1B32D4975FF0774B7C44CBEAF6BD282044DD838413B51077B45062A28CE09048
```

## Remaining ac5102 boundary

The final 120 planned production-manifest gameplay/effect events are ac5102.
Their unique visual source set contains:

- 49 native 416x232 clips;
- eight native 512x288 clips.

They cannot be emitted as one linear catalog because that would require canvas
resizing or mix components with different native roles. The next checkpoint
must split the component catalogs by native size and record how their combined
coverage closes each source event. Neither layer may independently claim the
whole event until that coverage relation is explicit.
