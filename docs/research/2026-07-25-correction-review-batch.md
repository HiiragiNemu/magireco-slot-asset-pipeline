# 2026-07-25 P12/P18/P23 纠错人工审查批次

> 2026-07-25 人工播放更新：P12/P23 当前 4 个具体 JA/ZH 文件已被项目所有者
> 确认可用；P18 仍被 fail-closed 隔离。批准只绑定本文哈希，不恢复旧版，
> 也不把 P12 路线展示候选解释成一条自然路线。

## 结果

本轮最初产出 P12 JA/ZH、P18 none/JA/ZH、P23 JA/ZH，共 7 个 MP4。P18
人工播放失败后，当前统一审查入口仅保留 P12/P23 共 4 个 MP4：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  manual_review_candidates_v26_corrections_20260725\REVIEW_NOW_4_MP4
```

`README_REVIEW_NOW.md` 给出逐片重点区间；`MANIFEST_SHA256.json`
SHA-256 为
`847DB95371651651EA8921E66485F016356E83B4ED3101768355542FB1801369`，
绑定当前 4 个成品。大型媒体不进入 GitHub。

四个具体文件的人工批准记录位于
`tools/frida_runtime_probe/owner_attestations/
owner_playback_approved_p12_p23_ac0908_20260725.json`。当前可用不等于由 Codex
投稿；用户仍自行决定后续投稿。

## P12

新的 `ac4902_audience_deduplicated_route_showcase_v1` 从 46 个原始单事件中选择
24 个唯一观众 occurrence；原始档案不删除。它是 route-aware 变体展示候选，不冒充
单一自然路线。自动 QA 通过 9,922 帧、330.733 秒、416x232、30 fps。

两句 `くそっ！/可恶！` 位于 00:09.633 和 04:12.933，只对
`ac4902_003/_059` request 8340 使用已授权黑羽身份覆盖。

```text
JA DF3346E45C59DCFBAE566913A9D9D6EE9B0569375B7C2062991F09DD0D9D37E8
ZH 6F7D031DE5A4A08E433B9441DB70F82DD400C9E9F565C5BE2372E23BAD836302
QA B9C8F906195054E921D896BA7EE8EDB07964B48CC214B0AFFBC5B800D6B04A16
```

## P18

路线顺序只采用 DirInfo v3 kind 173 row 10：

```text
ac6005_010 → ac6005_013 → ac6005_014
```

DirInfo CSV SHA-256：
`44202FCB8186D9577C33A4A20C492CFC84BFDD94DEC4EE76EB22DF8F4444DC01`。

`ac6005_014` composition plan 使用原生 512x416 故事层：

```text
c01       0–1333
c03    1333–2667
c04    2667–4167
c05    4167–9833
c06    9833–14467
c06_LP 14467–15333
```

独立的 320x256 `ac8040_shouri_EF_large/middle` 及 unresolved add 层属于胜利／
玩法效果，不进入干净剧情版。request 225 是 18.315 秒才开始的
`バトル勝利ジングル`，按 no-BGM 合同排除。requests 1029/2184 场景 SE 与
2793/2794/2795 对白保留。

`_010/_013` 为 416x232，在最终 512x416 路线画布居中补黑边，像素不缩放；
`_014` 保持原生 512x416。全片 941 帧、31.366667 秒、H.264 yuv420p、AAC
48 kHz stereo。三版 AAC packet SHA-256 完全相同：
`28420C93BF8AEB2DACDCD33263B0D2A00E130D6B2D379F003369A2839EB73844`。

```text
none D06DE03FD23B5EF8B267141ECE0E1DB596EAEBD520FABBAD7C274F223FBA7161
JA   DCD58F978093AA401752E6623911888ECBF370AD964DFE52F02B0979EF5601FA
ZH   DE095E2BC8F1A56D09FF9B642A092B14D00DACEF33B3C706B2DD71A83629B438
QA   6DB18E8D9BDD5AEF4230642ECCD3A5211EC8F23CFB2FAE2235C90C55FA16ABAE
```

这是有限静态证据 composition 候选，不是人工批准的最终版。项目所有者完整播放后
确认它严重失败：角色嘴动时没有声音／字幕，声音与字幕又出现在对应嘴动前，并疑似
漏掉对白。因此三版均已从审查入口移至：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  manual_review_candidates_v26_corrections_20260725\
  QUARANTINE_REJECTED_P18_20260725
```

`REJECTION_STATUS.json` SHA-256 为
`35BC5419986A5A2D45478E731E7260022BD428E260C7F0D7675C29F166CD5736`。
`ac6005_cu_success_route_v1` 现为 fail-closed，禁止渲染或投稿，直到各对白、
声音、嘴型和字幕的事件全局时间全部用证据闭合。

## P23

`ac7117_identity_corrected_series_v1` 保持 11 个原事件顺序、4,381 帧、
146.033 秒、512x288、30 fps。只对授权的 request 9634/9635/9638/9663 标注
`黒/黑`；`kuroe` 继续标注 `黒江/黑江`。人工重点为
00:02.247、00:04.877、00:25.400、01:07.933。

```text
JA 009875BA723DC597D517C8736D4078AB1D570126E1BDE3CFC48D663F4510EF11
ZH 183948615FA074D4E4EE8C525D002226A4A2C27D044FEA1B83D68D4456673720
QA 2DA06F2A3F6D9646B17B580FB2B9C9BD1E91CFA2BCF7305B35FD0C48002BC7C2
```

## 投稿隔离与继续生产边界

P12、P16、P18、P23 的旧 none/JA/ZH 共 12 个硬链接已移至
`quarantine_pending_fix_20260725`。P17 `ac6004` 随后因人工播放发现嘴型与
语音／字幕严重错位而整体隔离；活跃目录各剩 10 个 family。

P17 的精确根因不是编码漂移：`005→006→008→011→012` 中仅 request 3265
有 resolved runtime timing；其余 6 个对白起点只有 child-local callback 时点。
旧管线还漏掉 `_006` 的 request 3260（7.899 秒官方语音）。新的 production
manifest 门禁会在缺少父 DGM→子 Z2D 实例化偏移时 fail-closed；修复必须校验
expected request set 并逐 request 绑定父级偏移，禁止统一目测平移。

项目所有者已完整确认并由本人投稿 P11/P13/P14/P15/P19/P20/P21/P22/P24/P25
的 10 个具体 ZH MP4。精确文件名、字节数和 SHA-256 见上传根
`audit\HUMAN_PLAYBACK_APPROVALS_ZH_20260725.json`；文件自身 SHA-256 为
`62B9E9EC7B0BC65AE3D4F23298C1A547FE5215FEDB0F473E9597C275531D514C`。
none/JA 未获自动批准。

P16 尚未修复。运行时已完成恢复，但仍只能使用统一 Frida 17.16.4、真实 slot
主画面出现后、ADB 最新 PID、单 host/session 的轻量定向 probe；不得使用旧的
inject-before-Simulation 顺序或任何进程枚举。恢复记录位于
`D:\magia\MyProducts\casino\runtime_recovery_20260725\
RUNTIME_RECOVERY_FRIDA_17_16_4.md`，文件 SHA-256 为
`3B62A80DA4C26D4CB5EF2D1CB8D128DB41CC8E75C810C1C094C79D5272A03880`。

不受影响 family 的恢复提案保存在
`series_proposals/no_bgm_unaffected_families_resume_v1.json`。下一扩产
项目所有者停止新增 512 尺寸生产；后续以原生 416x232 选项路线为核心。
`ac7101–ac7107` 暂停。ac0908 六条 DirInfo 路线已完成有限批次，详见
`docs/research/2026-07-25-ac0908-option-route-review-batch.md`。它们同样只有
child-local cue，现仅为 timing-risk 人工候选，不是 READY；ac6002 仍须先证明
选项、路线结构与 event-global 声音时序，不能按 event 编号机械串接。
