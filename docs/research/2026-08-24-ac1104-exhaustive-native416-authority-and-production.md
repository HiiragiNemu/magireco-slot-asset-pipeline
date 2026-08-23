# ac1104 原生 416×232 穷尽长片权威化与生产检查点

## 状态

- 家族：`ac1104`（香蕉船对决）
- 产品单位：一部跨互斥路线、按可理解顺序编排的完整事件呈现合集
- 自动状态：`AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED`
- 人工状态：待项目所有者播放；未批准投稿
- BGM：有意排除经 `SOUND_DIVIDE_TBL` 证明为 BGM 总线的两次 request 229 / sound 554；保留 81 次已验证 VOICE/SE
- 输出：原生 416×232、30fps、H.264、AAC 48kHz stereo；无 upscale

## 代码级覆盖

`DirInfo` kind 56 的 15 条路线覆盖 17 个事件。通过 exact Z2D MovieLayer 表与同一运行时父 scene/motion capture 连接后，闭合：

- 17/17 完整事件呈现；
- 19 个父 Z2D；
- 46 个可加载 DGM 身份；
- 64 次按事件展开的可加载画面源出现；
- 4 个仅 authored、代码表中不可加载的 `_add` 名称，其同区间 base twin 均保留；
- 52 次 reqSound 回调与 2 条无语音图形文本；
- 54 条 event-global 字幕；
- 2 次 BGM 总线排除；
- 完整 AV/字幕呈现精确重复数为 0。

旧 43 源库存已被证实遗漏 `ac1104_017` 的 7 个主画面源，因此不再作为完整性权威。旧 `ac1104_017` 音频表还把 request 6214 错放到 302 帧并漏掉 request 2677；新 authority 分别绑定为 159 帧与 302 帧。

`ac1104_lev_c020_fukkatu_win_LP` 的官方源只有 5 帧，而父 Z2D authored 区间为 23 帧。新产品遵守“不重复独特视频内容”的编辑合同：源内容播放一次，后续只保持末帧，不把 5 帧循环扩写成新的独特内容。

## 耐久产物

- 运行时父级证据：`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\runtime_ac1104_story_scene_motion_v122r1_20260823`
- Z2D 提取：`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\ac1104_z2d_layer_authority_v123_20260823`
- 画面可达性：`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\ac1104_movie_layer_reachability_authority_v124_20260824`
- 音频/字幕总线：`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\ac1104_event_audio_authority_v125_20260824`
- 不可变输入：`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\ac1104_exhaustive_longform_inputs_v126_20260824`
- 三版生产：`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\no_bgm_editions_v126_ac1104_exhaustive_authoritative_20260824`
- 人工验收入口：`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\manual_review_hub_v2_flat\releases\native416_exhaustive_new_standard_v126_20260824`

三版均为 4221 帧 / 140.700 秒。`PRODUCTION_VERIFICATION.json` 记录三个精确 SHA-256 和媒体参数。验收入口含 17 个内容组、17 个主验收文件、39 个语言/素材入口，全部是同盘 hardlink；没有新增物理媒体副本，P16/P17/P18 泄漏为 0。

## 边界

本检查点只证明 ac1104。它不把旧库的 `REVIEW_READY` 自动升级为符合新标准的代码级完整性批准。其余原生 416×232 family 仍须逐项复核；AUTO QA 也不等于人工播放批准。
