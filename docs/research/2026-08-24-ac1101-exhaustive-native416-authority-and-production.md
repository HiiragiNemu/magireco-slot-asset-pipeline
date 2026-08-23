# ac1101 原生 416×232 穷尽长片权威化与生产检查点

## 状态

- 家族：`ac1101`（沙奈猫锅挑战）
- 产品单位：一部跨互斥入口、选项与结局，按可理解顺序编排的完整事件呈现合集
- 自动状态：`AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED`
- 人工状态：待项目所有者播放；未批准投稿
- BGM：有意排除两次经 `SOUND_DIVIDE_TBL` 证明为 BGM 总线的 request 229 / sound 554；保留 49 次已验证 VOICE/SE
- 输出：原生 416×232、30fps、H.264、AAC 48kHz stereo；无 upscale

## 代码级覆盖

`DirInfo` 的 31 条路线覆盖 13 个事件。exact Z2D MovieLayer 表、同一运行时父 scene/motion capture 与 runtime-exact reqSound 证据闭合：

- 13/13 完整事件呈现，完整 AV/字幕呈现精确重复数为 0；
- 17 个 exact 父 Z2D、20 个运行时父/次级绑定；
- 49 次 authored MovieLayer、39 个 authored DGM 身份；
- 35 个代码可加载 DGM 身份，4 个不可达 additive alias；
- 51 次按事件展开的可加载画面源出现；
- 22 次事件音频组件、29 次 runtime-exact 对白、2 条图形文本延续；
- 49 次保留的 VOICE/SE、31 条 event-global 字幕、2 次 BGM 排除；
- child-local-only 时序为 0，P16/P17/P18 泄漏为 0。

旧 36 视频库存遗漏了 3 个代码可加载源：`ac8000_cmn_tx_tuduku`、`ac8000_cmn_tx_tuduku_LP`、`ac8040_kyo_anten`，已标为 `WITHDRAWN_INCOMPLETE`。旧 ac1101_002 音频表中 request 4314 的父起点未解析；新 authority 使用同一运行时 event-global frame 1 证据纠正，不采用统一目测平移。

官方 `ac1101_lev_title_red` / `ac1101_lev_title_wht` 源均为 150 帧，但父 Z2D authored 区间只有 60 帧。渲染器现在只允许用 exact authored 前缀裁切官方源，禁止延长至源外或事件外；这保留父层编排而不凭视觉猜测。

## 耐久产物

- 运行时父级证据：`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\runtime_ac1101_story_scene_motion_v127_20260824`
- Z2D 提取：`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\ac1101_z2d_layer_authority_v128r1_20260824`
- 画面可达性：`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\ac1101_movie_layer_reachability_authority_v129r1_20260824`
- 音频/字幕总线：`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\ac1101_event_audio_authority_v130_20260824`
- 不可变输入：`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\ac1101_exhaustive_longform_inputs_v131_20260824`
- 三版生产：`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\no_bgm_editions_v132_ac1101_exhaustive_authoritative_20260824`
- 人工验收入口：`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\manual_review_hub_v2_flat\releases\native416_exhaustive_new_standard_v132_20260824`

三版均为 2851 帧 / 95.033333 秒。`PRODUCTION_VERIFICATION.json` 记录三个精确 SHA-256 和媒体参数。验收入口现在含 18 个内容组、18 个主验收文件、42 个语言/素材入口，全部是同盘 hardlink；没有新增物理媒体副本。

## 边界

本检查点只证明 ac1101。旧库存尚未整体按新标准完成代码级权威化或人工验收；`AUTO QA` 不等于项目所有者播放批准。其他原生 416×232 family 继续逐项复核，512 系保持低优先级。
