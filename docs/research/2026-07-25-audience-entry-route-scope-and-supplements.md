# 2026-07-25 audience 入口路线范围审计与补全候选

## 审计范围和判定

本轮只复核现有 audience 长产品、当前 v24/v25 production manifests 与 DirInfo；
没有扫描全部 926 个事件，也没有按事件编号缺口自动拼片。证据基线：

- `dirinfo_event_routes.csv` SHA-256：
  `44202FCB8186D9577C33A4A20C492CFC84BFDD94DEC4EE76EB22DF8F4444DC01`；
- `audience_event_catalog.csv` SHA-256：
  `2BC2F3BD17A3B7FCBA94D7D6AD29C80B5ABE0D72BEF38651EC9E999AEE346EFC`。

判定严格分三类：

- A：公共或必经入口／连接段遗漏，现有长产品的 composition 不完整；
- B：互斥入口、选项或终局未纳入，应另产独立路线／章节；
- C：玩法、外框、粒子、效果或 component-only 层，不进入干净剧情版。

机器可读风险表：
`tools/frida_runtime_probe/series_proposals/
audience_entry_route_scope_audit_20260725.json`。

## 已投稿产品的结论

确认 A 类问题：

- P13 `ac4903`：当前从 `_002` 开始，但 kind 114 rows 0–21 均从公共 `_001`
  开始；`_007/_016/_018` 是其他分支入口，必须分章节；
- P19 `ac6007`：漏公共 `_001`，且把 row0 与 row1 两条互斥路线平铺；
  `_001` 是多层 416 事件，先做正式 composition plan；
- P24 `ac7206`：第一入口组漏 `_001`，又把两个入口组和十二个互斥结果平铺；
- P25 `ac7210`：当前 `001→004→005` 不是任何 DirInfo 路线；row0 应为
  `001→002→003→004`，row1 应为 `001→005→003→004`。

没有发现同类公共入口直接遗漏：P11 `ac0911`、P14 `ac5301`、
P15 `ac5303`、P20 `ac7112`、P21/P22 `ac7113`。其中若有未纳入项，仍须按
B/C 分类，不能据编号补拼。

以上结构审计不撤销用户对已投稿具体 MP4 的片内播放确认，也不覆盖这些文件。
补全版一律使用新版本化根。

## ac0908 v28

补全候选：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  manual_review_candidates_v28_ac0908_complete_showcase_zh_20260725\
  REVIEW_NOW_1_MP4\
  ac0908 六种菜品入口补全参考合集__zh.mp4
```

- SHA-256：
  `53C0A918C043F78D8CB70DC643747C7DEC3FC45D5FA107A91251A347586AFD51`；
- `manifest/SHOWCASE_MANIFEST.json` SHA-256：
  `F77FFFF0674D41DAC7CFC9A7357EA8DF6B4C1FB9A2152E2261E7FD631DF05C4B`；
- `qa/AUTOMATED_QA.json` SHA-256：
  `04F47F309D0CBB425F1C62DD4A81F46FED2AB96EB1CF44605D31125C9F53DEA6`；
- `REVIEW_NOW_1_MP4/MANIFEST_SHA256.json` SHA-256：
  `3FAC6584AB661542A843C02A9FFB4731F39B3F2C1BB294ABA8816905EBFDCB52`；
- 2,745 帧、91.500 秒、原生 416x232、30 fps、H.264/AAC 48 kHz stereo；
- 参考视频只决定跨路线编辑顺序与 `ac0908_001` 入口呈现时长，没有取用其
  画面或音频；
- 当前状态：
  `REFERENCE_DERIVED_ALL_OUTCOMES_SHOWCASE_HUMAN_REVIEW_REQUIRED`。

人工重点：开头饭店外景后必须进入侧身炒菜；六道菜顺序为
`002/003/004/006/005/007`；最后评分 `_008` 只出现一次。该片不是一次游戏
自然 session，原六条 ZH 路线分段继续保留。

## P25 ac7210 v29

两个互斥路线候选：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  manual_review_candidates_v29_p25_ac7210_route_supplements_zh_20260725\
  REVIEW_NOW_2_MP4
```

| route | 顺序 | 时长 | SHA-256 |
| --- | --- | ---: | --- |
| row0 | `001→002→003→004` | 30.800 s | `8927CFDF7497B63B4FA47D7D9DB0C340FC837596547F3B9F4E8E15C764079088` |
| row1 | `001→005→003→004` | 37.366667 s | `990407DD95ABC18911782AFA9F2EC7AA3E2F17997BA9F716892D1AFFB1A06849` |

`SUPPLEMENT_MANIFEST.json` SHA-256 为
`3BE75ADC29B257D1678EE0CE7FECCB7EA1AA89404FFB014AA710A5A9BF5DCE5E`；
`REVIEW_NOW_2_MP4/MANIFEST_SHA256.json` SHA-256 为
`0097F0456CFAE9F59871A059904AAA8C2B84498318FDDA155F4B72B16F108EF0`。

`_002` 的画面 6.000 秒、父场景声 7.750 秒；`_003` 的画面 4.166667 秒、
父场景声 7.375 秒。当前没有同-run证据证明声音应跨到下一事件，候选按声音尾部
保持最后一帧，故状态为
`PRESENTATION_BOUNDARY_RISK_HUMAN_REVIEW_REQUIRED`。人工重点复看两处尾帧
边界，以及 `_004/_005` 的嘴型、语音和字幕；确认前不得投稿。

下一安全顺序是 P13 `ac4903`、P24 `ac7206`、P19 `ac6007`，再处理 P12
`ac4902` 路线目录；每一项仍须先闭合独立路线与 component 分类。
