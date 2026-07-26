# Owner-Approved Mixed Chapters Upload Checkpoint v37

Date: 2026-07-26

## Result

Four exact ZH chapter files from the durable v22 review root are restored to the
active upload guide. The project owner previously played all four files in full
and approved their exact media hashes. This checkpoint re-verifies the MP4,
subtitle, chapter manifest, automated QA, and READY hashes against:

```text
tools/frida_runtime_probe/owner_attestations/
  mixed_composition_4_chapters_owner_playback_20260718.json
```

The exact files are:

| Release | Native media | Exact video SHA-256 | Suggested part |
| --- | --- | --- | --- |
| `ac1102_full_no_bgm_zh_review_v1` | 416x232, 30 fps | `F2236AC4B3235C645E7408539E37AF2422077D8300C9EED2339CE73E15561BD2` | 菲莉希亚牧场完整章节（含已验证效果） ac1102 |
| `ac1103_full_no_bgm_zh_review_v1` | 416x232, 30 fps | `C1789C88415FEE6F52A4702B62A2F79ABB5877BAC55BE4681F56E27AC2BE5B1C` | 鹤乃外送修行完整章节（含胜利效果） ac1103 |
| `ac1104_full_no_bgm_zh_review_v1` | 416x232, 30 fps | `44CB183FE70CB384995582453D76F06F2CEFD95216D888245566D961AAA51053` | 海滩香蕉船完整章节（含已验证效果） ac1104 |
| `ac5208_full_no_bgm_zh_review_v1` | 512x288, 30 fps | `55875D4C661B2A6A5FEC077A2D3235C04AF98DC264DA104A2258C29E7392626D` | 三组魔法少女追击攻击 clean story ac5208 |

All four have H.264 video and AAC 48 kHz stereo audio. BGM is intentionally
excluded while the verified voice and scene SE are retained. Approval binds
only these exact ZH MP4 hashes. It does not approve none/JA siblings, event
extractions, or rerenders.

## ac1103_013 standalone blocker

`ac1103_013` is the strongest remaining native 416 gameplay/effect candidate:
its timed multilayer composition, dialogue, SE, and subtitle timeline all have
official runtime evidence. A pre-render validation nevertheless failed closed
for two precise representation gaps:

1. official adjacent voice requests 4058 and 4059 are represented by one
   runtime-merged subtitle cue, while the current family-edition builder models
   one request ID per cue;
2. request 1086 is the official CLEAR base sound, but the current hash-bound
   audio-role override registry has no dedicated scene-SE entry for it.

Request 4059 must not be mislabeled as scene SE to bypass the gate. No standalone
none/JA/ZH files were produced. The blocked proposal is:

```text
tools/frida_runtime_probe/series_proposals/
  ac1103_013_gameplay_effect_outcome_v1.json
```

The existing exact owner-approved ac1103 ZH chapter remains valid and ready; the
blocker applies only to a new standalone or sibling-edition build.

## Exhaustive ledger v6

The ledger now indexes the four exact approved products and their 40 unique
event occurrences without clearing the current v20 event-manifest timing-risk
flags:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  production_ledger_v6_20260726
```

This preserves both facts: the exact watched chapter is approved, while its
approval cannot be generalized to arbitrary event rerenders. The index and
summary hashes are:

```text
OWNER_APPROVED_LEGACY_PRODUCT_INDEX.json
  ED6CCAFD1865E920231DBA603C71ED25B0B17DD07FA6FE84D3988D67CD70E45D
SUMMARY.json
  9D2C5F32DFFA3C0E15A8C7763CA45CBFB5D9B92F517486715B8EF7093612C91A
SHA256SUMS.json
  EBB6CDE07E3DE840C73FF9FA356F69EB03EAECCCD787AF281765C9563863AA6A
```

P16/ac6003, P17/ac6004, and P18/ac6005 remain quarantined.
`ac7210_superseded_verbose_audit` remains audit-only and excluded.

## Upload guide v37

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  upload_guide_v37_20260726
```

The guide contains 198 exact files: 10 already uploaded, 17 ready to upload,
171 requiring human playback, and 8 explicit exclusions. The four v22 ZH
chapters are the only newly ready files in this checkpoint.

```text
UPLOAD_GUIDE.json  4104818D650A94A982F4FB04EADABF1E755AF624EE1F6D3CE9072BBEAFB4170D
UPLOAD_GUIDE.md    7A968BF1022496619FF95195707BF970D5A218FE67F401E14E6A5E627371E37B
UPLOAD_GUIDE.csv   73E486329647E8F2FDCAE81772810D6CFD130D86E3533C66767D967D13895FD5
SHA256SUMS.json    0C2A72972A1B48E29805DDAAFFB47B7359F77684ABD755C58666974CD5392F6F
```

Codex does not upload media.
