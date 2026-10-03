# 2026-08-02 统一人类生产入口与 v59r2 控制面

> ARCHIVED CHECKPOINT, NOT CURRENT. Counts and paths below describe 2026-08-02 only. See docs/PROJECT_STATUS.md for the later pointer and content contract.

## 结论

项目已把分散在版本化媒体根中的当前精确成品，统一映射到一个供人类审查和
上传的入口：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\00_BILIBILI_统一入口
```

旧媒体、manifest、QA、hash 和失败证据没有移动或删除。统一入口中的 MP4
全部是同卷 hardlink，不是复制品，也没有重编码。机器控制面与人类视图分开，
从而避免继续让数百个历史顶层目录干扰日常检查。

## 权威路径

| 角色 | 路径／标识 |
| --- | --- |
| Git 工作树 | `C:\Users\proje\.codex\worktrees\2fe8\com.universal777.magireco-Ga9DaxEd9F9Lqn9OVKVSfw==` |
| Git 分支 | `codex/corrected-runtime-pipeline` |
| 耐久媒体根 | `D:\magia\MyProducts\casino\magireco_corrected_research_20260612` |
| 稳定机器指针 | `D:\magia\MyProducts\casino\magireco_corrected_research_20260612\CURRENT_PRODUCTION.json` |
| 当前控制面 | `D:\magia\MyProducts\casino\magireco_corrected_research_20260612\_PIPELINE_MACHINE_ARCHIVE\checkpoints\unified_control_plane_v59r2_20260802` |
| 当前人类入口 | `D:\magia\MyProducts\casino\magireco_corrected_research_20260612\00_BILIBILI_统一入口` |
| 当前总账 | `production_ledger_v27r1_metadata_fix_20260730` |
| 当前上传指南 | `upload_guide_v59r2_unified_20260802` |

## v27r1 与 v59r2 的职责

`production_ledger_v27r1_metadata_fix_20260730` 是全局库存／生产覆盖总账。
它继承 v27 的媒体、分类和计数，仅把 `ac4903_015` 的 blocker 精确改为分层
组件合成缺口，因此不会造成另一路生产。当前总账为：

- produced audience events：195；
- material-covered events：634；
- produced DirInfo routes：79。

`upload_guide_v59r2_unified_20260802` 是全局人类状态和上传索引。它把每个
具体文件按 SHA-256 绑定到唯一状态、标题和路径；它不重复生成媒体。当前为：

| 状态 | 精确文件数 |
| --- | ---: |
| 已投稿勿重复 | 11 |
| 已审查可上传 | 18 |
| 待人工审查 | 318 |
| 合计 | 347 |

另有 8 条显式排除记录，不进入人类媒体目录。控制面绑定的重要哈希为：

```text
ledger SUMMARY.json
708EC0F5265EB69EAD11DEE375A6365B35A0CD78731C7AC8923DE9B7429CD2DB

ledger CURRENT_PRODUCTION_MANIFEST_INDEX.json
ABE93B17C913C1ECDEB5B79E3BEE2C09A3A7DDF74D82E9EB7B5CF03CF4E47707

ledger CURRENT_MATERIAL_COLLECTION_INDEX.json
DC276BCC05A1FE22FE7C32943D6059A443E7BC57935C296BD84F443904DE76C9

guide UPLOAD_GUIDE.json
6EA70F468742D8D7C3B0D17763E0CB800EF5D6FA420F96BB670E625BD95FCAD9

guide SHA256SUMS.json
4F423696AECD3A170C658351A5ED4CA865F75C63CF3EB35DB352E9D22039AC46
```

## 人类目录合同

```text
00_BILIBILI_统一入口\
  00_今后只打开此目录.txt
  00_上传指引.md
  01_已审查可上传\
    zh\  jp\  none\  material\
  02_待人工审查\
    zh\  jp\  none\  material\
  03_已投稿勿重复\
    zh\  jp\  none\  material\
  04_隔离禁止上传\
```

该目录只提供人类需要的 MP4 和文字入口，不放 JSON/CSV 审计噪声。347 个
MP4 的状态分布与 v59r2 guide 完全一致。44 个 material 均是单一 canonical
文件，而不是 none/JA/ZH 同哈希别名。

## U144/U145 精确纠正

| 项目 | 当前语义 | 当前状态 | SHA-256 |
| --- | --- | --- | --- |
| U144 Magius 白色阶段玩法组件 | 416×232 `standalone_visual_catalog` | 已审查可上传 | `D9E47A1F98CF5311AE4FC434D55ECE3EB6BD035CB3BD633D7205A574012F9259` |
| U145 Magius 暗转叠加组件 | 208×120 `layer_component_material` | 已投稿勿重复 | `F71CA6911169A142C6DE1F9F7A5209AD2A69850E7CA1DFF69954589DDB4D489C` |

精确人类路径：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\00_BILIBILI_统一入口\01_已审查可上传\material\U144_Magius白色阶段玩法组件_ac4906.mp4

D:\magia\MyProducts\casino\magireco_corrected_research_20260612\00_BILIBILI_统一入口\03_已投稿勿重复\material\U145_Magius暗转叠加组件_ac4906.mp4
```

U145 单独观看时很短且播放语义依赖叠加，这只改变
`presentation_role`，不等于废弃素材。旧 v59 U144/U145 的 none/JA/ZH
三轨包装全部被 `superseded_by_single_visual_canonical`；素材本体和来源
provenance 均保留。

## 发布与媒体边界

- no-BGM 和 with-BGM 是两条独立生产轨。no-BGM 有意排除 BGM，保留已有
  证据闭合的角色对白和 SE；不能据此声称原游戏没有 BGM。
- with-BGM 必须绑定曲目、入口 phase、原生音量、fade/duck/stop、来源哈希
  和路线时间线；研究它不得改变已稳定的 no-BGM 媒体。
- 原生 416×232 family/route 优先，但 512×288、512×416、208×120、
  192×320 等同样按原生画布保存。禁止 upscale、拉伸、补边或跨尺寸机械
  concat；不同画布只有在分层时序和 blend/z-order 均有证据时才合成。
- 没有语言差异的纯视觉素材只产生一个 `material`。确有对白或字幕差异时，
  才建立 none/JA/ZH。
- P16/ac6003、P17/ac6004、P18/ac6005 继续硬隔离。child-local Z2D 时间
  不得晋升为 event-global。自动 QA 不等于人工播放或投稿批准。

## v60r1–v65 尚未合并的 59 项

生产线程随后完成了 v60r1–v65 共 59 个单轨 material MP4（U146–U204）：

| 批次 | 产品数 |
| --- | ---: |
| v60r1 | 11 |
| v61 | 10 |
| v62 | 10 |
| v63 | 10 |
| v64 | 10 |
| v65 | 8 |
| 合计 | 59 |

这些项目已经通过原生尺寸、30 fps、无 upscale、无音轨、source rehash、
manifest/output SHA、跨批 source 去重和 P16/P17/P18 零泄漏门禁；但状态仍是
`HUMAN_PLAYBACK_REQUIRED`。截至本记录，它们尚未进入 v59r2 的 347 文件
统一入口，也尚未加入当前 44 个分 P 名单。

下一版操作必须是一次事务：将 v60r1–v65 的 delta 纳入新总账和 upload
guide，排除已 supersede 的旧 v60 试验根，重新校验全部来源与状态，重建
统一 hardlink 视图，再替换稳定 `CURRENT_PRODUCTION.json`。禁止手工往当前
人类目录塞入这 59 项，否则机器索引、上传状态和人类目录会再次分叉。

## 保留与回滚

本次统一没有删除或移动历史目录。机器控制面、guide 和 human view 都可由
绑定的计划、旧版本化媒体根及 SHA-256 重新生成。任何失败都应保持旧稳定
指针和旧人类入口不变；新检查点只有在全量 hash、状态、隔离和 hardlink
验证通过后才可晋升。
