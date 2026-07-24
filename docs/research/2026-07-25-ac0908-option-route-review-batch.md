# 2026-07-25 ac0908 原生 416x232 选项路线审查批次

## 结果

按项目所有者最新优先级，停止新增 512 尺寸生产，先完成一个原生 416x232、
带选项且路线独立的有限批次。最终人工审查成品共 18 个 MP4：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  manual_review_candidates_v27_ac0908_option_routes_20260725\
  REVIEW_NOW_18_MP4
```

`MANIFEST_SHA256.json` SHA-256：
`8DD03A8D8C7EFBEDC515F0EB7D78F8B1BC80CDD61449210B2D643F6007D079AF`。
目录中的 18 个文件是六条路线各自的 none/JA/ZH。生产根另有 24 个单事件检查片
和母版，因此递归统计为 42 个 MP4；内部文件不属于投稿清单。

该目录当前明确标为
`AUTOMATED_SPEC_QA_PASSED_TIMING_RISK_HUMAN_REVIEW_REQUIRED`。根目录
`TIMING_RISK_STATUS.json` SHA-256：
`91D44761921497807FE253D577D3C578D63A37B203AE49865AC10E36609C1950`。
这 18 个文件不是 READY、不是量产成功，也不得进入投稿准备根。
内容计数应为 6 条路线、每条 3 个 edition，而不是 18 部不同内容。

## 路线

DirInfo v3 CSV SHA-256：
`44202FCB8186D9577C33A4A20C492CFC84BFDD94DEC4EE76EB22DF8F4444DC01`。
只采用 kind 33 rows 52–57，每条路线独立：

| row | 路线 | 帧数 | 时长 |
| --- | --- | ---: | ---: |
| 52 | `009 → 002 桃包 → 008` | 650 | 21.667 秒 |
| 53 | `009 → 003 中华海蜇 → 008` | 650 | 21.667 秒 |
| 54 | `009 → 004 天津饭 → 008` | 650 | 21.667 秒 |
| 55 | `009 → 005 韭菜炒肝 → 008` | 650 | 21.667 秒 |
| 56 | `009 → 006 麻婆豆腐 → 008` | 650 | 21.667 秒 |
| 57 | `009 → 007 四千年套餐 → 008` | 581 | 19.367 秒 |

没有把六个互斥菜品事件串成一部长片。所有事件保持原生 416x232、30/1 fps，
H.264、AAC 48 kHz stereo，无 resize、pad、crop 或 upscale。

## 路线证据与旧自动门禁

上游路线目录 `ac0908_dirinfo_route_catalog_v1.json` SHA-256：
`A409707C7E7DE35E723F9DE901AAA09C4EA90F70498A5C1842B5BBE23470F5F6`。
六条路线均绑定 v20 事件 manifest 的 SHA-256，声音只保留当时被标为 voice 与
scene SE 的层；每条 6 个对白 cue、9 个 audio layer、0 个旧格式
`unresolved audio`。下列 QA 是收紧时序门禁之前的规格 QA 结果，只能证明编码、
文件和既有 manifest 的自洽，不能证明对白 cue 已落在事件全局时间。

自动 QA SHA-256：

| row | QA SHA-256 |
| --- | --- |
| 52 | `1494317A935CC82FAD9AB29DDAB8039BA954E52638702B90C79FAD0FFD7F720D` |
| 53 | `DBB83A4FADE303C952F14354A65CFBC23FE92C52F823B9A08F95E8A69F622F80` |
| 54 | `D64521EC4B44DED919865913544ED96F1A85A9567CBEF1480A20D6A9F3C699F0` |
| 55 | `6550399204B6E4B77D926088C59DE46B20632E08AE9295F6E9FAC80D55EC3021` |
| 56 | `574CC87A69726AD25630182F92B19D2F4C43C96594F42A1EA1F6D9F1933C376C` |
| 57 | `B8BF2B4CD7301240ECD8C34049726D613189E57E396A842603D4FEB4E0920ED9` |

六条当时均通过 source hash、proposal identity、无重复 audience event、原生尺寸、
帧／采样网格、AAC 单次编码与三版 packet 一致、字幕 round-trip 等门禁。当前
proposal 已改为 `timing_risk_manual_candidate`，因此这些旧 QA 不再允许重用为
生产 READY 证明。

## 事件全局时序风险

只读复核确认 `ac0908_002.json` 至 `_009.json` 的
`runtime_event_manifest_sources` 全部为 null；当前耐久 runtime sequence/probe
根也没有这些事件的 resolved `event_manifest.json`，并且没有父 DGM 创建子 Z2D
的事件全局实例化偏移。所有对白 cue 仅由
`exact_gdb_child_frame_callback_frame_and_official_ogg` 给出：

| event | child-local cue |
| --- | --- |
| `_002` | req3501 +200 ms |
| `_003` | req3502 +200 ms |
| `_004` | req3503 +200 ms |
| `_005` | req3504 +200 ms |
| `_006` | req3505 +200 ms |
| `_007` | req3506 +1333 ms |
| `_008` | req3512 +167 ms；req2601 +2333 ms；req3513 +5400 ms |
| `_009` | req3497 +200 ms；req3498 +1500 ms |

这些数字证明子 Z2D callback 的局部帧，不证明它们在父 DGM 事件中的全局起点。
六条路线均必经 `_009` 与 `_008`，所以全部共享该风险。旧
`validation_outputs_v15_ac0908_food_sample` 的 `_003/_006/_009` 使用同一 cue
时点，且曾被项目所有者认为视觉可接受；这支持保留有限人工候选，但不能替代
parent-offset 证据。

## 人工审查边界

当前 `human_playback_approved=false`、`publication_approved=false`，并新增
`event_global_z2d_timing_ready=false`。ZH 翻译
文件 `ac0908_option_routes_zh_dialogue_v1.json` 仍标记
`machine_draft_pending_owner`，不得把自动 QA 当成人工翻译或嘴型批准。

先看六个 ZH：

- 全部路线约 00:04.633 进入各自菜品事件；
- rows 52–56 约 00:13.633 进入 `008` 评分结果；
- row 57 约 00:11.333 进入 `008`；
- 重点确认嘴型、语音起点、字幕起止和最后评分对白。

P17 `ac6004` 的人工失败说明规格 QA 不足以证明语义音画正确。本批只适合有限
人工检查，不得因视觉上“似乎可接受”而晋升；若人工发现任一路线错位，继续隔离，
不得统一目测平移。

若六条路线今后全部通过人工时序验收，仍须保留六个独立分段；在此基础上可以再做
一部“六种菜品路线合集”长版。合集不能替代六个分段，也不能在时序未通过时先做。
