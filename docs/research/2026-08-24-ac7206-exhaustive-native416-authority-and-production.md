# ac7206 原生 416×232 穷尽长片权威与生产检查点

## 结论

`ac7206` 的干净剧情产品已按“同一 family 内全部可达、完整且不重复的
画面+声音+字幕呈现各保留一次”闭合。它不是原生单局调度声明，而是便于
全视频收集的可理解编辑合集。

- DirInfo：40 个精确行，20 个不同事件序列，12 个不同剧情路线投影。
- 全 family：15 个事件，其中 14 个剧情事件进入长片；`ac7206_015` 是独立
  玩法叠层，仍等待 selector/component 合成与外部音频上下文，未混入剧情。
- 14 个剧情 AV 呈现全部唯一；视觉投影只有 8 组。6 对事件复用同一官方
  画面，但使用不同的精确对白/字幕，所以不是完整 AV 重复，必须分别保留。
- 12 个官方 H.264 原生 416×232/30fps DGM 源、19 次剧情源呈现均已绑定。
- 严格 no-BGM：保留 28 个 VOICE/SE，排除 `request226/sound551` 的 2 次
  BGM；14 条对白均使用 event-global 父级起点。
- 旧 137.8 秒 fragment 集合包含 35 次源出现、仅 10 个源身份和 25 次冗余，
  且缺入口，继续作为撤回证据，不是当前权威成品。

## 耐久产物

- 画面权威：
  `D:\magia\MyProducts\casino\magireco_corrected_research_20260612\ac7206_movielayer_reachability_authority_v134_20260824`
- 声音/字幕权威：
  `D:\magia\MyProducts\casino\magireco_corrected_research_20260612\ac7206_event_audio_authority_v135_20260824`
- 长片输入：
  `D:\magia\MyProducts\casino\magireco_corrected_research_20260612\ac7206_exhaustive_longform_inputs_v136r1_20260824`
- 三版成品：
  `D:\magia\MyProducts\casino\magireco_corrected_research_20260612\no_bgm_editions_v137r1_ac7206_exhaustive_authoritative_20260824`
- 单一人工验收入口（第 19 组）：
  `D:\magia\MyProducts\casino\magireco_corrected_research_20260612\manual_review_hub_v2_flat\releases\native416_exhaustive_new_standard_v138_20260824`

## 媒体结果

三版均为 54.000 秒、1620 帧、416×232、30fps、H.264/AAC 48kHz stereo：

- none：`8A8C88CBA3B6ED44A8DEAED500597CA40575E18FEBC1AA9AEC02DE7C2E3BD5F3`
- JA：`40FDB2A88889FE39D789DF832A813FEC74A54A3BEA3C844B2943022A5F80F8F8`
- ZH：`013392A2C4EDB0063A83E45256127D3163B880352823F3A4411D08AA9F940670`

`v138` 有 19 组内容、19 个主审文件、45 个语言入口。全部为同盘硬链接，
没有新增物理媒体副本；P16/P17/P18 与 `ac7206_015` 均零泄漏。

## 人工边界

自动 QA 已通过，但新长片尚未获得人工播放批准。旧 P24 人工结论只覆盖
其中复用的三条中文文本，不自动批准新时间线。`ac7206_001` 的“干得漂亮，
灯花、音梦。”仍是待确认译文；请以 v138 的 G019 ZH 长片整体播放结果为准。

首次渲染因翻译映射状态词不符合现有加载器合同而在媒体生成前停止，失败根
`no_bgm_editions_v137_ac7206_exhaustive_authoritative_20260824` 已保留失败记录；
修正后的 v136r1/v137r1 已完整重建、解码并验证。
