# ac7210 原生 416×232 穷尽长片权威与生产检查点

## 结论

`ac7210` 已按代码级 DirInfo、runtime scene/motion、Z2D MovieLayer、
`SOUND_DIVIDE_TBL` 与父级 event-global 时点闭合原生 416×232 剧情产品。
最终成品是“全视频收集”的编辑长片，不声称属于一次原生单局：两条互斥接近
路线都被保留，但每个独一画面+声音+字幕呈现只出现一次。

- 5 个 DirInfo 行覆盖 `ac7210_001..008`。
- `001..005` 是原生 416×232 剧情集合；编辑顺序为
  `001→002→005→003→004`。
- `006..008` 使用 512×416/component/玩法终局，已记录但按项目优先级延后，
  没有混入当前 416 剧情长片。
- 14 次已编写剧情 MovieLayer 中，`ac7210_002_c03_LP_MR` 与
  `ac7210_002_c03_MR` 的官方 MP4 字节完全相同。前者保留一次，后者作为
  authored alias 省略；当前产品共 13 个独一官方源呈现。
- 严格 no-BGM：10 个声音实例全部由 `SOUND_DIVIDE_TBL` 证明为 6 个 SE、
  4 个 VOICE，BGM 为 0。
- 4 条对白/字幕全部使用父级 scene 起点加 child callback frame 的
  event-global 精确时点；没有 child-local-only 时点。
- `ac7210_AT_ibu_cap_title`、`ac8040_kyo_anten` 与 512/320 玩法叠层继续作为
  独立效果/组件边界，不伪装成干净剧情。

## 耐久产物

- 画面权威：
  `D:\magia\MyProducts\casino\magireco_corrected_research_20260612\ac7210_movielayer_reachability_authority_v140r1_20260824`
- 声音/字幕权威：
  `D:\magia\MyProducts\casino\magireco_corrected_research_20260612\ac7210_event_audio_authority_v141_20260824`
- 长片输入：
  `D:\magia\MyProducts\casino\magireco_corrected_research_20260612\ac7210_exhaustive_native416_longform_inputs_v142r1_20260824`
- 三版成品：
  `D:\magia\MyProducts\casino\magireco_corrected_research_20260612\no_bgm_editions_v143r1_ac7210_exhaustive_native416_authoritative_20260824`
- 当前唯一新标准验收入口：
  `D:\magia\MyProducts\casino\magireco_corrected_research_20260612\manual_review_hub_v2_flat\CURRENT_NATIVE416_EXHAUSTIVE_REVIEW`
- 本次主验文件：
  `ZH\story\G020_ac7210_八千代与鹤乃火箭突击 全分支·全结果完整合集__zh.mp4`

## 媒体结果

三版均为 1354 帧、416×232、30fps、H.264/AAC 48kHz stereo，时长约
45.133 秒：

- none：`893B941F8FE9CB25EE229F9B3E076F3E657C3839A161E372510594AABC9BE4F8`
- JA：`8A3268102D1F28B55AABBA671EE60E566A76D82ACB87749FF632E44A886810E6`
- ZH：`65AF3D66677EB4433B9552AD854A9DAFC1E6232CF3BDC9A704894D61571CD914`

新 v144 审查发布共 20 组内容、20 个主验文件、48 个语言入口。全部为同盘
NTFS 硬链接，未创建物理媒体副本；P16/P17/P18、512 终局和独立叠层零泄漏。

## 人工与失败边界

旧 ac7210 两条路线的人工批准只覆盖旧精确文件/哈希和已复用文本，不自动
批准这条新去重长片。新 G020 仍为 `HUMAN_PLAYBACK_REQUIRED`。

首次 v143 尝试在任何媒体生成前被翻译加载器拒绝，因为八千代与鹤乃共享
同一句日文“きゃぁぁっ”。失败根保留为 `FAILED_DO_NOT_USE`。v142r1 将相同
日中译文合并为单一翻译键，人物名前缀仍分别由 `yac`/`tur` 证据生成；
v143r1 已完成三轨渲染、完整解码与自动 QA。

此前库存没有被整体提升为“按新长片标准人工通过”。旧 exact-hash 人工批准
仍然有效；v144 中重新权威化的长片逐组保持待人工播放状态。
