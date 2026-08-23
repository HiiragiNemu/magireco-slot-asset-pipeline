# ac1103 全路线长片复核检查点（2026-08-24）

## 结论

- DirInfo `kind=55` 的 31 行已全部解析，覆盖 13 个原生 416x232 event presentation。
- 用户此前质疑的 18 秒 `ac1103_013` 只是一章/证据片段，不是最终独立产品；当前长片将 13 个完整 presentation 各收一次，时长 3114 帧（103.8 秒）。
- 53 个视觉 occurrence 归并为 35 个字节唯一来源；源层别名不等于完整 AV/subtitle presentation 重复。13 个完整 presentation 的精确重复数为 0。
- 12 个 child Z2D 事件均已由 hash-bound parent scene motion key 解析 event-global 起点；`ac1103_013` 使用已有 runtime-exact manifest。child-local-only 接受数为 0。
- request 229 在 `_006` 与 `_013` 中被 SOUND_DIVIDE_TBL 证明为 BGM 并排除；57 条对白/SE 与 33 条字幕保留。

## 当前成品

- 原成品：`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\no_bgm_editions_v121r1_ac1103_exhaustive_authoritative_20260823`
- 统一双组审查入口：`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\manual_review_native416_authoritative_longforms_v1_20260824`
- ac1103 在 NONE/JP/ZH 下各一个同盘 hardlink；未移动、删除或转码源媒体。
- 自动 QA：通过；人工完整播放：待确认；投稿：未批准。

精确 SHA-256、媒体验证、代码绑定和回滚记录见 `ac1103_exhaustive_authoritative_longform_v151_20260824.json` 与 D: 的 `VERIFICATION_RECORD.json`。
