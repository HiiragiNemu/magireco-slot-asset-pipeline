# Project Status

更新时间：2026-07-03

## 2026-06-26 v18 当前状态

当前生产分支是 `codex/corrected-runtime-pipeline`。下载目录中的旧 `main`
检出不是权威工作树。

`production_manifests_v18` 当前覆盖 926 个事件，其中 521 个 render-ready、
405 个 failed、683 个 composition-resolved、405 个 audience-excluded、1615 条字幕。
当前 failed 全部有 audience exclusion reason；非排除 failed 队列为 0。
所有新增正式输出继续遵守：原生分辨率/帧率、不 upscale、不生成旧 124GB 1080p 输出、
不使用旧 motion/static 分类、不按 `ac` 后缀数字推 CRI index、不混合字幕版/无字幕版、
老虎机/按钮/粒子素材与正常动画分离。

最新新增：

- 2026-07-02 ac7116 renderer texture-state 探针已新增：
  `docs/research/2026-07-02-ac7116-renderer-texture-state-probe.md`。
  新工具包括 `runtime_symbol_survey.js`、`cri_video_texture_probe.js` 和
  `summarize_cri_video_texture_probe.py`。全模块符号 survey 找到比
  `GLtask_display1/2` 更贴近实际路径的内部 renderer 符号：
  `RendererImplGL::checkAndBindTextureStates`、`TextureStateGL::bind`、
  `CScreenObjectMng::draw/calcFrameControl` 以及
  `CriVideo::GFDirectionRenderer::*`。GL export/eglGetProcAddress/OES draw
  探针只看到 0.074-0.080 s 与 6.707-6.715 s 的 512x288 texture
  allocation/bind/delete；11.267-13.05 s 语音尾段没有普通 GL texture upload、
  bind/delete、draw/sync/swap 证据。重启 app 并 reinject Gadget 后的 combined run
  位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_video_texture_ac7116_v5_combined_after_restart_20260702`：
  同一 run 中捕获主故事 `1e31c4fa`/1955904/512x288/30fps/338 帧，以及
  `sprite_renderer_check_bind_texture_states` 在 9-11 s、11.267-13.05 s、
  14-20 s 继续触发，且三段窗口均为同一 renderer/texture-state tuple
  `0x72b10b97f910` + `0x72af3cccff78` + flag `1`。该证据把
  `ac7116_001` 的 hold 从“动画对象/CRI receiver 支持”提升为“renderer path
  仍持续活动且状态稳定”支持；但仍不是 framebuffer/clean-layer pixel hash，最终
  B站投稿仍需 clean-layer pixel/texture proof 或明确接受该机制证据，outer-flow BGM
  门禁也仍未解除。2026-07-03 继续在
  `texture_state_fields_ac7116_v2_after_restart_20260703` 中加入
  `TextureStateGL` 前 0x80 字节的 metadata-only 数值字段采样；同一 run 再次捕获主故事
  `1e31c4fa`/1955904/512x288/30fps/338 帧，并在 11.267-13.05 s 尾段捕获
  20 次 `sprite_renderer_check_bind_texture_states`。三个 texture-state 指针
  `0x72af42645f58`、`0x72af42645f78`、`0x72af42646148` 均在尾段持续出现，
  且关键字段如 `+0x4=3553`、`+0xc=3`、`+0x68=194423728` 等保持稳定；
  其中 `+0x4=3553` 与 `GL_TEXTURE_2D` 一致，但结构布局未完全命名，不能直接把单个
  offset 当成最终 pixel proof。随后 `cri_video_texture_probe.js` 继续加入
  `RendererImplGL::drawCall(Primitive*)` primitive metadata 采样，v8 可用 run 位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_video_texture_ac7116_v8_primitive_after_restart_taps_20260703`：
  同一 run 捕获主故事 `1e31c4fa`/1955904/512x288/30fps/338 帧和 280 次
  renderer drawCall；在 11.267-13.05 s 尾段仍有 19 次
  `checkAndBindTextureStates` 与 19 次 `drawCall`。尾段保持同一 renderer
  `0x72b10b9830a0` 下的单纹理四顶点 primitive
  `0x72af405bd370`/`0x72af405bd168`/`0x72af405bd148`，分别带 texture id
  `155`/`151`/`150` 的稳定签名。该证据进一步证明游戏 renderer path 在主 338 帧后
  的语音/字幕尾段仍持续提交稳定 primitive，支持当前 clean `hold_last_frame` 策略；
  但仍不是 clean-layer framebuffer/pixel hash，且同 run 的 `89802b19`
  512x416/5277 帧 receiver 仍必须标记为 slot/gameplay/material 状态，不能当作 clean
  story continuation。已用同一 v8 JSONL 额外生成
  `summary_fine_windows`，确认三组稳定 primitive 在 0.5-6.6 s 主段、6.6-7.2 s
  LP 切换、7.2-11.0 s 中段、11.267-13.05 s 尾段和 14-20 s 后段均持续出现；
  该细分 summary 用于后续 layer correlation，仍不能直接命名 clean story primitive。
- 2026-07-03 继续从 static symbol survey 转向更直接的 Z2D movie-layer 路线：
  新增 `tools/frida_runtime_probe/z2d_movie_layer_probe.js` 与
  `tools/frida_runtime_probe/summarize_z2d_movie_layer_probe.py`，报告补充在
  `docs/research/2026-07-02-ac7116-renderer-texture-state-probe.md`。符号调查确认
  `zg::CZ2DPlayer::ExecPlayMovie`、`CZ2DHardPlayer::DecodeMovie/DrawMovie`、
  `CZ2DPlayMovie::*`、`CZ2DElemMovie::*` 与
  `CriVideo::GFDirectionCriPlayer::*` 是比旧 frame-lock hooks 更接近实际 movie
  调度的路径。forced `ac7116_001` v1 捕获位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\z2d_movie_layer_ac7116_v1_20260703`，
  `summary_v2` 识别到一个 512x288、start/end frame 0/337、decode frame 固定
  337、`IsDrawTime(337)=1`、texture-like id `151` 的 Z2D movie 对象；它与 renderer
  primitive `0x72af405bd168` / texture id `151` 对应，并在 11.267-13.05 s
  语音/字幕尾段继续 `ExecPlayMovie`、`GetDecodeFrame`、`DecodeMovie` 和
  `drawCall`。这把 `ac7116_001` 尾帧 hold 从“renderer stable primitive”提升为
  “Z2D movie-layer 以 end frame 337 原生持帧”强证据。随后按 force-stop/start/
  reinject/title-flow taps 重跑 v2，路径为
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\z2d_movie_layer_ac7116_v2_same_run_closure_20260703`：
  同一 run 在 121 ms 捕获主故事 `1e31c4fa`/1955904/512x288/338 帧，并命名
  `ac7116_AT_SP_story5_01.dgm` 的 Z2D 对象 `0x72affb9c0ae8` /
  `0x72affb9c0a98`，start/end frame 0/337，尾段 `IsDrawTime(337)=1`、
  `GetDecodeFrame(337)=337`，texture-like id `153`，renderer primitive
  `0x72af4e66e168` / texture id `153` 持续 drawCall 到 25.8 s。`ac7116_001`
  视觉尾帧 hold 现在应视为 runtime-mechanism 级闭环证明；BGM/outer-flow 门禁仍未解除，
  ac7114/ac7115 仍需同路线扩展。不要再把旧高层 frame-lock hook 作为主路线。
  随后同一 Z2D route 已扩展到 `ac7114_001` 与 `ac7115_001`，报告记录在
  `docs/research/2026-07-02-ac7114-16-cri-receiver-tail-sampler.md`。`ac7114`
  同 run 命中主故事 `a5b2c906`/1903456/512x288/275 帧与
  `ac7114_AT_SP_story3_01.dgm`，Z2D 对象 `0x72affba47728` /
  `0x72affba476d8` 在尾段 `IsDrawTime(274)=1`、`GetDecodeFrame(274)=274`，
  primitive `0x72af4e66e168` / texture id `165` 持续 draw。`ac7115` 同 run
  命中主故事 `4ad69770`/3940544/512x288/636 帧与
  `ac7115_AT_SP_story4_01.dgm`，Z2D 对象 `0x72affb9d0c28` /
  `0x72affb9d0bd8` 在尾段 `IsDrawTime(635)=1`、`GetDecodeFrame(635)=635`，
  primitive `0x72af4e66e168` / texture id `197` 持续 draw。至此
  `ac7114_001 + ac7115_001 + ac7116_001` clean story 的 visual tail-hold gate
  在 runtime-mechanism 级别已解决；下一关键门禁是 BGM/outer-flow audio proof。
- 2026-07-03 `visual_tail_probe.js` 以已恢复 Gadget 状态重跑 frame-lock 路线，结果位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\visual_tail_lock_ac7116_v10_20260703`。
  事件与 runtime 两侧均 exit 0，`summary_animation` 显示 88 个样本从 18 ms 覆盖到
  21829 ms，selected source 全部为 `C_AnmMain+0x350`，selected object
  `0x72b06b9870c0`、frame object `0x72b06b987510` 全程不变，`last_frame_age_ms`
  17-51 ms，selected object `+0x350` 从 4289 单调增到 4944。负证据同样重要：
  已安装的 `DirGetFrame`/`NotifyMovieStart`/`NotifyStartAnim`/`GetFrameInfo`/
  `IsFrameReady`/`CScreenObjectMng` lock-draw 高层 hook 在该 run 中全部 0 calls；
  runtime receiver 也只重捕获 foreground/gold-frame `c8fd6fe7`、`72e6f81c`、
  `c9cc7d28`、`f32a4a6b`，没有主故事 `1e31c4fa`。因此 v10 不能作为 main-clean
  identity proof；后续不要重复同一高层 hook set，应转向已知会触发的 lower renderer/
  compositor path 或 clean-layer texture/framebuffer hash。
- 2026-07-02 ac7116 animation-state sampler 已新增：
  `docs/research/2026-07-02-ac7116-animation-state-sampler.md`。
  新版 `event_scene_probe.js` 在 forced event context 活跃时每约 250 ms 输出
  `animation_state_sample`。成功捕获位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\animation_state_sampler_ac7116_v10_after_recovery_20260702`。
  结果：`ac7116_001` 从 16 ms 到 16817 ms 共 68 个采样，11.267-13.027 s
  声音/字幕尾段期间仍为 `C_AnmMain+0x350`、selected object
  `0x72b06b9bacc0`、frame object `0x72b06b9bcf40`，`last_frame_age_ms`
  保持几十毫秒。这证明官方动画系统在主 USM 338 帧结束后仍持续渲染同一故事动画对象；
  结合 v6 的主 USM 时长证据，`ac7116_001` 的 clean `hold_last_frame`
  现在可视为 runtime-supported mechanism-validation 行为，而不是纯外部拼接猜测。
  v11/v13 数值采样进一步发现 selected object `+0x350` 按约 30fps 单调递增，
  11.267-13.027 s 尾段不停止；该字段应视为动画对象时钟，不是 CRI movie frame
  index。v12 的宽泛 pointer scan 会导致 Frida/Gadget capture timeout，已将
  `includePointerProbe=false` 作为默认。仍未捕获 clean/story layer 的逐帧
  像素/texture 或 CRI frame index，所以最终 B站投稿仍受 clean-layer compositor
  proof 与 outer-flow BGM proof 门禁限制。新增通用解析脚本
  `tools/frida_runtime_probe/summarize_animation_state_samples.py`，用于把任意
  `event_scene_probe.js` 的 `animation_state_sample` JSONL 自动汇总为
  `animation_state_summary.json` 和 `animation_state_samples.csv`，避免后续继续手工
  逐个 ac 解析。随后 `visual_tail_probe.js` 新增 CRI receiver metadata sampler，
  并新增 `tools/frida_runtime_probe/summarize_cri_receiver_samples.py`。v16 重启 app
  并 reinject 后命中主 receiver `1e31c4fa`：512x288、30fps、338 帧，
  `cri_update` 覆盖 4-11134 ms，`GetStatus=5` 覆盖 267-10973 ms，receiver 数值采样
  到 20746 ms。该证据支持“主 CRI 到源时长后由上层动画/合成保持最后输出”，但仍不是
  clean-layer texture/pixel hash。
  同一方法已扩展到 `ac7114_001`/`ac7115_001`，报告位于
  `docs/research/2026-07-02-ac7114-16-cri-receiver-tail-sampler.md`：`ac7114`
  主 receiver `a5b2c906` 为 512x288/30fps/275 帧，`ac7115` 主 receiver
  `4ad69770` 为 512x288/30fps/636 帧。`ac7115` 另见 512x416/5277 帧大
  receiver `89802b19`，明确标记为非 clean story continuation。
- 2026-07-02 slot idle audio smoke 已记录到
  `docs/research/2026-06-28-audio-output-mechanism.md`：在恢复后的真实 slot
  gameplay 画面上分别运行 20 s `runtime_probe.js` 和 `csl_audio_queue_probe.js`，
  输出位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_idle_runtime_probe_20260702`
  与
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_idle_csl_queue_probe_20260702`。
  两者均没有非 hook 的 BGM/sound request 或 OpenSL play/enqueue 事件。这只证明当前
  idle slot 状态没有正在观测窗口内持续 enqueue 的 BGM，不能解除真实 story 触发路径的
  outer-flow BGM 门禁。
- 2026-07-03 `csl_audio_queue_probe.js` 已升级为同源 CSL+BGM 合并探针：同一次
  Frida run 同时记录 `libGameProc.so` 高层 sound-code/BGM helper 与 `libAMAIN.so`
  最终 `CSLAndroidSimpleBufferQueue::Enqueue` 队列，且单个高层 hook attach 失败不会
  中断后续 hook 安装。`summarize_runtime_audio_capture.py` 已适配该合并 JSONL 的
  sound-code/event-code 字段。验证捕获位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_bgm_combined_ac7116_v3_20260703`
  和
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_current_csl_bgm_combined_v2_20260703`。
  forced `ac7116_001` 同源捕获结果：38 个 hook 安装成功，`SndIsAlreadyPlayingBGM`
  1 个 attach error，BGM helper 行为 0，高层 sound-code 行为 13，最终 OpenSL queue
  仍只有 `42080_SPストーリー5_みふゆとももこ_01` / sound id `8912`、`8040_シネスコ変化音_金帯`
  / sound id `9544`、`31186_282_mihu_く…ぐ…` / sound id `8008` 三段。当前 live
  slot 状态 20 s 被动探针无 sound request、无 BGM helper、无 OpenSL enqueue。这强化
  forced ac7116 “无额外 BGM”结论，但仍不能解除自然 outer gameplay transition 门禁。
- 2026-06-28 ac7116 visual-tail 运行时探针报告已更新：
  `docs/research/2026-06-28-ac7116-visual-tail-runtime-probe.md`。
  v3 捕获位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\visual_tail_probe_ac7116_v3_20260628`，
  证明官方 `SetData` 命中了 gold-frame 前景层及 6.66 s 左右的 LP 前景切换：
  `AT_SPstory_gold_frame_add.usm`、`AT_SPstory_gold_frame.usm`、
  `AT_SPstory_gold_frame_add_LP.usm`、`AT_SPstory_gold_frame_LP.usm`。
  v6 在重启 app 并 reinject arm64 Gadget 后，直接观察到主故事
  `ac7116_AT_SP_story5_01.usm`
  (`patch_index=1321`, size `1955904`, first-4KiB FNV `1e31c4fa`) 的
  `CriManaWrapper::SetData`，且 `GetMovieInfo` 为 512x288、30 fps、338 帧
  （约 11.267 s）。这证明当前主视频源和时长是游戏运行时官方调度，不应换成旧
  416x232 restaurant/table 候选。但 v6 没捕获到 downstream frame/compositor
  证据，仍不能最终证明 clean 主画面在 11.267 s 后的尾帧 hold 是游戏原生；
  v7 官方 full-machine screenrecord 只证明前景 slot/title 层继续显示，不能代替
  clean/story layer 证明。`C_ObjNml::fnSndRequest_BGM_*` 的 per-frame helper
  调用也不是可听 BGM 证明。v8/v9 给 `visual_tail_probe.js` 增加了
  `split_config.arm64_v8a.apk` 模块解析和 offset fallback，能安装
  `GLtask_display1/2` hook，但这些 hook 在 forced event 窗口仍未触发，说明实际
  clean/story compositor 热路径还没打到。`csl_audio_queue_ac7116_v1_20260628`
  证明 forced official event 的最终 OpenSL 队列只有 request `42080`、`8040`、
  `31186`，无额外 BGM queue chunk；其中 `31186`/sound id `8008` 是 mono，
  `decode_csl_audio_queue_dump.py` 已新增默认 per-chunk 声道推断，避免把 4.144 s
  语音误判为 2.072 s。剩余 BGM 门禁现在是 outer gameplay/full-flow 捕获问题。
- 2026-06-28 交接与尾帧门禁修正：已新增核心交接文档
  `docs/HANDOFF_NEXT_AI_MAGIRECO.md`。用户确认
  `validation_outputs_v19_clean_audio_gate_ac7114_16_001_20260628` 的语音和字幕正确，
  但指出 `ac7116_001` 约 11 s 后画面静止、声音/字幕延续到约 13 s，且对是否缺
  BGM 存疑。复核结论：v19 没有删除 `420xx_SPストーリー...` bed/base-scene audio；
  `ac7116_001` 的静止尾巴来自 `hold_last_frame` 策略，保留最后角色语音
  `31186_282_mihu_く…ぐ…` 到 13027 ms。源 DGM `ac7116_AT_SP_story5_01.mp4`
  未检测到同等冻结，渲染版检测到 `freeze_start: 11.2`。因此当前 ac7114-16
  长片只能作为用户验证/机制验证输出，不能标为最终投稿成品；需要运行时画面或
  compositor/frame hook 证明尾帧 hold 是否为游戏原生行为，并继续用运行时 BGM/CSL
  queue 证据证明是否存在额外 BGM。
- `audit_runtime_av_trust.py` 已新增 `visual_tail_hold_ms`、
  `video_extension_policy`、`video_duration_ms` CSV 字段和
  `visual_tail_hold_needs_runtime_confirmation` 风险标记：角色语音事件若使用
  `hold_last_frame`/`black_tail` 且视觉尾巴 >= 750 ms，不再视为最终交付可信。
  v19 ac7114-16 子集重审位于
  `A:\magireco_corrected_research_20260612\runtime_av_trust_audits_v19_clean_audio_gate_tail_hold_20260628`，
  3/3 均保持 `blocked_pending_runtime_av_verification`；`ac7115_001` 与
  `ac7116_001` 命中新的尾帧确认门禁。全量 v18 manifest-only 重审位于
  `A:\magireco_corrected_research_20260612\runtime_av_trust_audits_v18_tail_hold_gate_20260628`，
  新门禁共命中 29 个事件。使用该 CSV 重算后的 strategy 位于
  `A:\magireco_corrected_research_20260612\pipeline_strategy_audits_v18_tail_hold_gate_20260628`；
  217 个 ready-missing 事件中仍只有 4 个 delivery-actionable，213 个保持 AV-blocked。
- 2026-06-28 clean-story 音频门禁修正：`audit_runtime_av_trust.py` 现在默认可全量审计
  manifest-root，区分 bed/base-scene audio、role voice 与 slot/foreground effect audio，
  并新增 `slot_or_foreground_effect_audio_in_clean_story_candidate`。全量 v18 manifest-only
  审计位于
  `A:\magireco_corrected_research_20260612\runtime_av_trust_audits_v18_clean_audio_gate_20260628`，
  926 个事件中 897 个仍被 AV 信任门禁阻塞，134 个命中 clean-story 中混入
  slot/foreground effect audio 的风险。
  使用该全量 AV trust CSV 重算后的 strategy 位于
  `A:\magireco_corrected_research_20260612\pipeline_strategy_audits_v18_clean_audio_gate_20260628`；
  217 个 ready-missing 事件中只有 4 个仍是 delivery-actionable，213 个转入
  `av_blocked_ready_missing_queue.csv`。
- `ac7114_001`、`ac7115_001`、`ac7116_001` 的 clean composition plans 已明确排除
  request `1681` / `8040_シネスコ変化音_金帯`，因为它属于被排除的 gold-frame/foreground
  slot 演出音效，不属于正常动画上传版。修正后的 production manifests 位于
  `A:\magireco_corrected_research_20260612\production_manifests_v19_clean_audio_gate_20260628`；
  修正后的单事件双版本位于
  `A:\magireco_corrected_research_20260612\validation_outputs_v19_clean_audio_gate_ac7114_16_001_20260628`，
  标准 QA 3/3 通过、非静音、字幕/无字幕音频一致、512x288、30/1、48 kHz 双声道。
- 已新增 `tools/frida_runtime_probe/build_scene_editions.py`，用于显式事件序列的同场景长片；
  旧 `build_series_editions.py` 只支持单 `acXXXX` 前缀 family，不适合 `ac7114 + ac7115 + ac7116`
  这种跨前缀同场景。已生成可审计 review 长片：
  `D:\MagiReco_Reverse\magireco_verified_scenes_v19_clean_audio_gate_20260628\ac7114_16_sp_story_clean_audio_gate`，
  含字幕版/无字幕版、合并 SRT、`scene_manifest.json`、`audit\scene_index.csv`、源文件 hash 和累计时间轴；
  scene-level QA 通过，3 段、44.854 s、10 条字幕、512x288、30/1、48 kHz 双声道。
  该输出用于用户验证；角色口型/视觉语音一致性仍按 AV trust gate 保持为最终交付前门禁。
- `ac5208_001`、`ac5208_002` 和 `ac5208_003` 已转为 clean story composition plans，
  剥离黑幕 `ac8002_chance_btn*` 按钮层和对应按钮提示音/押して声；`ac5208_003`
  采用主攻击层 `ac5208_lev_madhom` 归零、`ac5208_lev_madhom_LP` 从 4167 ms
  接续，并按官方 `40006_特化ﾏﾐ_追撃_まどほむ攻撃` 音频结束点渲染到 6740 ms；
  同时补入官方 request `8367 / 28016_CV_見滝原まだまだだよ` 字幕；
- `ac5208` 三个追击 clean story 单事件双版本已通过 3/3 QA；同场景长片候选也已
  stream-copy 生成并通过脚本 QA/视觉抽查，保持 512x288、30/1、48 kHz 双声道和
  双版本音频一致；
- 输出目录：
  `A:\magireco_corrected_research_20260612\validation_outputs_v18_clean_story_ac5208_full_v2`；
  长片目录：
  `D:\MagiReco_Reverse\magireco_verified_series_v18_clean_story_ac5208_20260626`；
- `ac2201_001` 已审计为 `黒江狙え` slot/gameplay cut-in，含押し順/狙え文字层和
  ADD/MUL 特效层，现从 clean story 队列排除并保留为素材/玩法候选；
- 57 个非 ready 的 `ac3102` RB slot battle/gameplay UI 事件已批量从 clean story
  队列排除，样本 `ac3102_007` 确认角色层自带按钮/图标/玩法文字；
- 24 个非 ready 的 `ac3103` RB roulette/gameplay UI 事件已批量从 clean story
  队列排除，样本 `ac3103_001` 确认叠层包含調整屋文字/图标/角色剪影玩法 UI；
- `ac5102_003` 已按静态生产证据转为 clean attack animation composition plan，
  渲染字幕/无字幕双版本并通过 1/1 QA；视觉抽查确认是伊吕波 magiatack 角色动画
  和粉色冲击背景，不含按钮、押し順、狙え或老虎机 UI 文本层；
- 19 个同结构 `ac5102` native 416x232 短攻击动画已小批量恢复，均为角色
  intro/LP 加同编号 `uwa_ef_bg_lp` 攻击背景，字幕来自官方 voice label，
  渲染字幕/无字幕双版本并通过 19/19 QA；输出目录为
  `A:\magireco_corrected_research_20260612\validation_outputs_v18_clean_story_ac5102_safe_shape_batch`；
- 剩余 120 个 `ac5102` mixed-dimension button-prompt 事件已从 clean story 队列排除，
  它们全部含 512x288 `ac8002_chance_btn_*` PUSH/連撃/長押し/連打玩法按钮层；
  保留为 gameplay/material collection 候选，不纳入正常动画长片；
- 6 个 `ac5004` Connect Chance title/selection UI 事件已从 clean story 队列排除，
  它们是 `コネクトチャンス` 标题和颜色抽选 UI，不属于正常剧情/动画成片；
- 24 个 `ac3407/ac3409` card-flip 上乗せ/PUSH UI 事件已从 clean story 队列排除，
  它们是 `ac3403_mekure_3on_*` 卡牌翻转和 `押して！` gameplay prompt；
- 15 个 `ac4904` SU/window framed character presentation 事件已从 clean story
  队列排除；角色内容位于小窗/卡框 UI 中，保留为 material/gameplay 候选；
- 16 个 `ac5201` 决战神浜黑底角色台词/动作事件已恢复为 clean animation，
  渲染字幕/无字幕双版本并通过 16/16 QA；输出目录为
  `A:\magireco_corrected_research_20260612\validation_outputs_v18_clean_story_ac5201_ch_serif_batch`；
- 20 个 `ac9051` 連撃 button-prompt UI 事件已从 clean story 队列排除；
  它们是纯 `ac8002_chance_btn_rengeki` / LP 按钮提示、PUSH 显示音和押して声，
  应保留为 gameplay/material collection 候选；
- 42 个 `ac0912` small-Kyubey guide / CHANCE / 激アツ / WIN / 上乗せ presentation
  事件已从 clean story 队列排除；抽样渲染 4/4 通过仅作为分类证据，视觉审计确认其为
  slot/gameplay guide 素材，不纳入投稿用正常动画长片；
- `ac0912` material collection 已生成并通过 manifest QA，保留 24 个去重组件、
  416x232、30/1 原生素材视频；另有官方音频可听审阅版，音频只来自当前 manifest 的
  官方事件音频证据；
- `reproducibility/project-kit/` 已建立，用于索引非 Python 探针/配置/清单、
  大型输入 fingerprint-only 策略和公开 Release 的派生证据边界。
- 2026-06-28 已发布 text-only derived evidence release
  `analysis-evidence-v18.27-20260628`：
  `magireco-analysis-evidence-v18-20260628-100858.zip`，12,765,785 bytes，
  SHA-256 `2D440A240CEF5A2A7F08D0B4FDE6D356A10CAF80655CA5E8370657000AD06797`。
  Release URL：
  `https://github.com/HiiragiNemu/magireco-slot-asset-pipeline/releases/tag/analysis-evidence-v18.27-20260628`。
  本地 bundle audit：1,599 个 evidence files、0 个 disallowed/media/binary
  extension、0 个绝对本机路径 pattern match；内容只包含 CSV/JSON/MD/TXT/SRT 派生证据，
  不含 `.jsonl` 原始 Frida 捕获、WAV、截图、视频、APK/OBB/native 库或游戏 payload。
- 2026-06-27 纠偏：用户复核确认 `ac0921_001` 缺预期 BGM，`ac4901_025/026`
  存在角色未张嘴但有语音/字幕的问题，`ac7204` material/result 输出含角色语音、
  不能称为纯素材；因此 technical QA/contact-sheet 不能再作为交付充分条件。
- 已新增 `tools/frida_runtime_probe/invalidated_output_roots.json`、
  `audit_runtime_av_trust.py`，并让 coverage/strategy 脚本读取作废根和 AV 信任审计；
  作废根保留在磁盘上用于审计，但不再计入完成覆盖。
- 通用化 pipeline 策略报告已重算，当前结论是：217 个 ready 但缺单事件 QA 的事件中，
  213 个仍是 linear full-frame 视频组合候选；但后续只能作为机制验证/批处理输入，
  不能在缺少运行时完整 BGM/SE/voice、字幕和视觉语音一致性证据时晋升为投稿成片。
- 2026-06-27 继续修正：`runtime_probe.js` 已补入高层声请求 hook，包括
  `C_CtrlSndLib::fnReqSndEventCode`、`fnReqSndSoundCode`、
  `fnReqSndSeqenceSC`、`fnReqSndSoundCodeCallBack`、
  `SoundMng_play_bySoundCd` 和 `SndReqBySoundCd`。这用于验证 `ac0921_001`
  这类静态 event timeline 缺 BGM 的样本是否由游戏全局/序列声调度层播放音频。
- `resolve_official_event_capture.py` 现在会输出 `actual_play_sound_count`、
  `high_level_sound_request_count`、`unresolved_sound_event_count` 和
  `unresolved_sound_events.csv`。高层声请求无法映射到 request/OGG 时必须显式保留为
  unresolved evidence，不能被当作完整音频轨。
- 新增 `diagnose_runtime_capture_state.py`。当前 MuMu 诊断输出位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\capture_state_20260627`，
  结论为 `blocked_x86_frida_cannot_see_arm64_game_code`：x86 Frida 可 attach 进程壳，
  但看不到 arm64 `libGameProc`；27043 ARM64 Gadget 仍不可达；arm64 frida-server 在
  native bridge 下仍连接即关闭；旧 Java-layer Gadget injector 在 x86 attach 表面报
  `Java is not defined`。因此在 Gadget 恢复前不生成新的投稿样片或批量成片。
- 2026-06-27 realm 复测输出位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\capture_state_realm_20260627`：
  default/native realm 都只能看到 `x64` 壳，均无 Java bridge、均看不到 `libGameProc`；
  emulated realm 返回 `ProtocolError('process is not using emulation')`；包本身
  `primaryCpuAbi=arm64-v8a`、`ro.debuggable=0`。捕获工具已补 `--realm native|emulated`
  入口以便未来环境验证，但当前状态仍不能恢复官方运行时 AV 捕获。
- 2026-06-27 Gadget 恢复：旧会话中的可用路线已固化为
  `tools/frida_runtime_probe/reinject_gadget.py`，通过 x86 frida-server endpoint 运行
  `inject_gadget.js`，加载 app 私有目录中的 ARM64 Gadget。当前 smoke 输出
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\gadget_reinject_tool_smoke4_20260627`
  为 `ok=true`，`gadget_arch=arm64`，且通过 `_ZN8CScnSlot4CalcEv` 导出反推到游戏映射；
  后续诊断
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\capture_state_after_gadget_reinject_v3_20260627`
  结论为 `runtime_capture_ready_via_arm64_gadget`。这只恢复了官方运行时取证能力；
  `ac0921/ac4901/ac7204` 等被作废样本仍需重新捕获、解析和人工验证后才可重新渲染。
- 2026-06-27 官方 code 重新捕获报告已写入
  `docs/research/2026-06-27-runtime-av-recapture-report.md`，后续 BGM 缺口复核写入
  `docs/research/2026-06-27-runtime-bgm-gap-report.md`。关键结论：
  `ac0921_001` 必须用长窗口解析，官方运行时在约 74 ms 播放
  `2990_次回予告_レバー`，后续有 4 条 Iroha 语音/字幕，并在约 27.46 秒才加载
  `ac0921_jikai_yokoku_3on_01(.lp)`；旧 15 秒 resolver 窗口会漏掉后段画面。但用户
  复核确认该 runtime-repair 样片全程无 BGM、约 23 秒后无语音，因此它是失败诊断样片，
  不能作为投稿成片或旧 v18 batch 的恢复证据。
  `ac4901_025/026` 和 `ac7204_003/017` 均有官方角色语音，不得归入纯素材；
  其中 `ac4901` 视觉说话校验不通过时也不得归入 clean-story 投稿候选。
- `resolve_official_event_capture.py` 已把空字符串声回调改写到
  `ignored_sound_events.csv`，并把默认解析窗口改为 60 秒。真实未解析音频仍保留在
  `unresolved_sound_events.csv` 和 `unresolved_sound_event_count`，不能被忽略。
- `ac0921_001` 的第一条 runtime-repair 用户复核样片已降级为 failed diagnostic：
  production manifest 位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\production_manifests_runtime_repair_v1_ac0921\events\ac0921_001.json`，
  渲染输出位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\validation_outputs_runtime_repair_v1_ac0921\ac0921_001`。
  虽然技术 QA 曾显示 1/1 passed、32.766 秒、416x232、30/1、48 kHz stereo、
  字幕/无字幕音频哈希一致，但用户复核发现全程缺 BGM 且尾段无语音；因此 contact sheet
  / stream QA 不能作为交付充分条件。
- `event_scene_probe.js` 的 `--with-sound` 官方路径已修通并记录
  `forced_event_sound_request_sent`，但 `ac0921_001` 诊断证明手动 event sound 只会多打一条
  `2990_次回予告_レバー`，不会补 BGM；`capture_official_event.py` 因此保留
  `--with-event-sound` 为诊断开关，默认不额外请求 event sound。
- `runtime_probe.js` 已补 BGM/request 层 hook：`zgSndReqCode/FadeCode/VolumeCode/PauseCode`、
  `SoundMng_isAlreadyPlayingBGM`、`C_ObjNml::fnSndRequest_BGM_*`、
  `C_DirectionControllerBase::Macro_SND_BGM_PLAY` 等。`ac0921_001` BGM-hook 捕获位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\official_bgm_hook_smoke_20260627`；
  事件窗口只见 lever SE 和 4 条 voice request，没有 BGM request，说明单 event 强制触发
  不进入外层 BGM 状态机。后续必须捕获完整触发流程或游戏最终混音，不能继续只靠单 event
  拼接生成投稿成片。
- 已新增 `tools/frida_runtime_probe/audio_output_probe.js` 作为游戏最终音频输出路径的
  metadata-only 探针。有效数值 code smoke 位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\audio_output_probe_ac0921_numeric_smoke_20260627`：
  `OutputCtrl::output` 捕获 265 个样本，其中 210 个为 output-enabled、5 个
  `TransBuf` 头部非零；事件侧仍只有 lever SE 和 4 条 Iroha 语音，没有 BGM request。
  这证明游戏混音出口可 hook，但 `TransBuf` PCM 布局尚未验证，不能据此生成投稿音频。
- `event_scene_host.py`、`capture_official_event.py` 和 `event_scene_probe.js` 已加
  numeric code 防呆：`--code` 必须是 resolved GBoss uint64，例如
  `0x544549382d424c4d`，`ac0921_001` 这类名称只能放在 `--label`。这避免 RPC 报错但
  pending request 已进入游戏而污染证据。
- 用户继续复核确认 `ac0921_001__subtitles.mp4` 无 BGM/不可听；文件级 audit 证明
  MP4 虽有 48 kHz stereo AAC 音轨，但 23 秒后到 32.766 秒尾段为实质静音
  (`mean/max=-91.0 dB`)。`qa_event_batch.py` 已补
  `manifest_audio_tail_gap` 和 `tail_digital_silence_after_manifest_audio` 门禁；重跑
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\validation_outputs_runtime_repair_v1_ac0921`
  后 `ac0921_001` 从旧 technical passed 改为 failed，记录
  `manifest_last_audio_end_ms=22777`、`manifest_audio_tail_gap_ms=9989`、
  `tail_max_volume_db=-91.0`。
- 2026-06-28 声音机制进展已写入
  `docs/research/2026-06-28-audio-output-mechanism.md`。静态证据确认
  `SndSystem::updateOutputBuf()` 先四平面混音并调用 `OutputCtrl::output(system+0xf78, ...)`，
  `OutputCtrl::output()` 会先检查 `[this+0x10]` 输出设备指针；当前 runtime
  `sound_device_state_ac0921_numeric_v3_20260628` 在 35 秒窗口内 46/46 个输出样本均为
  `output_device=0x0`，其中 23 个样本仍为 `output_enabled=1`。因此现在的阻塞点是
  游戏最终音频设备/全局 BGM 触发链没有被完整复现，不是继续按视觉拼接单 ac 能解决。
  已新增 `audio_output_buffer_probe.js`、`decode_audio_output_buffer_dump.py` 和
  `sound_device_state_probe.js` 用于后续从进程启动/设备初始化阶段继续破解。
- 2026-06-28 后续突破：`docs/research/2026-06-28-csl-audio-queue-runtime-capture.md`
  记录了 `libAMAIN.so` 实际可听 one-shot 路线：
  `CSndMng::SndReq -> CSLMng::SndReq -> CSLMng::PlayStart ->
  CSLAndroidSimpleBufferQueue::Enqueue`。新增
  `csl_audio_queue_probe.js` 和 `decode_csl_audio_queue_dump.py`，可把 OpenSL queue
  chunks 解码为 concat 或 runtime timeline WAV。`ac0921_001` 复测得到 5 段真实入队音频：
  request `2990/30031/30032/30077/30078` 对应 sound id
  `6893/6930/6931/6976/6977`；`--with-sound` 只额外重复请求 `2990`，没有产生额外
  BGM buffer。诊断 WAV 位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_audio_queue_ac0921_post_slot_v2_20260628\ac0921_001_runtime_audio_timeline.wav`
  和
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_audio_queue_ac0921_with_sound_v3_20260628\ac0921_001_with_sound_runtime_audio_timeline.wav`。
  这证明单 event 强制路径有权威 SE/voice 时间轴，但仍没有证明完整 BGM；继续禁止把
  `ac0921_001` 晋升为投稿成片，下一步必须捕获外层 gameplay/BGM 状态机。
- 2026-06-28 真实 slot 输入机制捕获已写入
  `docs/research/2026-06-28-slot-gameplay-audio-state-machine.md`。在 MuMu slot 主界面
  发送最小 lever/stop-button 输入后，运行时 event code 解析到
  `ac0001_001/ac9902_001/ac9010_060/ac9071_001/ac9100_001/ac9903_001/ac9920_001/ac9071_002/ac0910_001/ac0910_002`；
  `runtime_probe` 同时记录到反复的 `C_ObjNml::fnSndRequest_BGM_*`、
  1 次 `C_DirectionControllerBase::Macro_SND_BGM_PLAY`，以及 sound code
  `301/302/303/304/305/814/295/271` 通过
  `zgSndReqCode -> RequestCtrl::codeName2ReqId -> SoundMng` 进入请求层。
  `csl_audio_queue` 最终 OpenSL 队列捕获 15 个 dumped PCM chunks、48 kHz stereo、
  约 15.48 秒，observed sound ids 为 `60/61/62/6758/6759/9002`；另有
  sound id `287` / code `814` 的 3,072,004-byte chunk 因 per-chunk dump cap 只记录
  metadata，需要小范围提高 cap 复抓。诊断听音 WAV：
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_gameplay_input_probe_20260628\slot_gameplay_runtime_audio_timeline.wav`。
  这确认游戏机制是 runtime event-code + sound-code/request 状态机，不是手工逐个
  `ac` family 视觉分类；后续 manifest 必须以运行时请求和最终 OpenSL/官方解码证据为准。
- `tools/frida_runtime_probe/summarize_runtime_audio_capture.py` 已新增，用于把
  `runtime_probe.jsonl` 与 `csl_audio_queue.jsonl` 规整成可审计 CSV/JSON 表，而不是靠
  contact sheet 或人工截图判断。首轮 slot 捕获和大块重采样均已生成 `summary_tables`；
  大块重采样位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_gameplay_input_probe_large_chunk_20260628`，
  在 8 MiB per-chunk cap 下捕获 25 个完整 OpenSL queue chunks、约 19.86 秒、
  无 metadata-only chunks，observed sound ids 为
  `60/61/64/291/864/1768/6698/6709/8573/8575/9002`。该 run 走到不同随机 gameplay
  分支（`ac0908/ac0909`），没有复现早先 `814/287` 分支；因此 `814/287` 仍需定向状态
  steering 才能作为最终音频证据。
- `tools/frida_runtime_probe/build_runtime_evidence_skeleton.py` 已新增，用于把上述
  summary tables 与 `event_timeline_events.csv`、`event_timeline_sounds.csv`、
  `sound_request_struct_requests.csv` 和 `sound_id_records.csv` 离线合并为
  `runtime_evidence_skeleton.json`、`event_sequence.csv`、`sound_code_sequence.csv`、
  `play_request_sequence.csv`、`queue_sequence.csv` 和 `static_event_sounds.csv`。
  输出明确标记 `evidence_only_not_render_ready`：首轮 slot skeleton 保留
  metadata-only 警告；大块重采样 skeleton 无警告。它是后续批量 manifest 生成前的
  证据层，不会自动把诊断捕获晋升为投稿成片。
- 2026-06-28 定向 slot 输入复抓位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_targeted_814_probe_20260628`：
  8 轮 lever/stop 输入捕获 47 个完整 OpenSL queue chunks、约 41.40 秒、无
  metadata-only chunks，observed sound ids 包含 `287`。运行时确认 `814` 在
  `ac0910_001` 活跃窗口触发，`sound_code_sequence.csv` 映射为 request table id
  `344` / `213B22458D11890FF6BEEC183F22.smz`；`queue_sequence.csv` 中
  `sound_id_u16_at_0x2=287` 的 3,072,004-byte chunk 映射到
  `snd_00814_bank01_ogg_00287.ogg`。这解决了首轮 `814/287` 只记录 metadata 的缺口，
  但仍属于 gameplay/slot 机制证据，不是正常动画成片。
- `tools/frida_runtime_probe/package_runtime_evidence_capture.py` 已新增，用于把一次
  runtime capture 固化成可复现证据包：重新解码 OpenSL WAV、生成 summary tables、
  evidence skeleton、`source_hashes.csv`、`cumulative_runtime_timeline.csv`、
  `qa_report.json` 和 `package_manifest.json`。定向 `814/287` 捕获的证据包位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_targeted_814_probe_20260628\evidence_package_v1`，
  QA 状态为 `passed_evidence_not_delivery`，12 个关键文件已写 SHA-256，累计时间轴
  128 行。首轮 slot 捕获也用同一工具生成负例证据包：
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_gameplay_input_probe_20260628\evidence_package_v1`，
  QA 状态为 `failed_evidence_package`，失败原因是 `queue_metadata_count=1` 和
  skeleton metadata-only warning；这证明门禁会阻止不完整音频证据进入渲染。
- `tools/frida_runtime_probe/audit_runtime_evidence_packages.py` 已新增，用于扫描
  `evidence_package_v*` 并生成 package index。当前审计输出位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\runtime_evidence_package_audit_20260628`；
  结果为 2 个 package：`passed_evidence_not_delivery=1`、
  `failed_evidence_package=1`。失败检查统计为
  `no_metadata_only_queue_chunks=1`、`skeleton_has_no_warnings=1`。
- `tools/frida_runtime_probe/build_runtime_evidence_promotion_queue.py` 已新增，用于把
  package index 转成保守晋升/隔离队列。当前输出位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\runtime_evidence_promotion_queue_20260628`：
  首轮 failed package 被标记为 `blocked_failed_runtime_evidence_package`；定向
  `814/287` passed package 被标记为
  `runtime_gameplay_or_slot_material_with_dialogue_audio`，`clean_story_status` 为
  `not_eligible_gameplay_or_slot_sequence`。因此通过运行态音频 gate 仍不会自动进入
  normal animation / Bilibili clean-story 渲染。
- `report_pipeline_strategy.py` 已接入可选
  `--runtime-evidence-promotion-csv`，把 runtime evidence package gates 纳入全局
  pipeline strategy summary/report。重算输出位于
  `A:\magireco_corrected_research_20260612\pipeline_strategy_audits_v18_runtime_evidence_gate_20260628`；
  当前仍为 926 个 production events、521 ready、217 个 ready-missing，其中
  166 个不被 AV gate 阻断、51 个 AV-blocked。新增 runtime package gate 统计为
  `failed_evidence_package=1`、`passed_evidence_not_delivery=1`，promotion lanes 为
  `blocked_failed_runtime_evidence_package=1`、
  `runtime_gameplay_or_slot_material_with_dialogue_audio=1`，clean-story eligibility
  为 `not_eligible=1`、`not_eligible_gameplay_or_slot_sequence=1`。
- `tools/frida_smz_wav_probe.py` 已修正为全模块查找
  `zgSndCaptureConvertWav*`，因为当前 ARM64 Gadget 中导出位于
  `split_config.arm64_v8a.apk`，不是单独的 `libGameProc.so` 模块名。直接转换
  code `814` / raw media `213B22458D11890FF6BEEC183F22.smz` 目前返回 0 且不写 WAV；
  反汇编显示该导出依赖 zgsnd `SndSystem` 全局（`zgSndWinDllConstruction` /
  `zgSndInit` 路线），而当前可听路径是 `libAMAIN.so` `CSLSound` / OpenSL。因此
  官方 game-decoder 转 WAV 仍是后续破解路线，不能替代当前 OpenSL queue 取证。
- `audit_runtime_av_trust.py` 已从粗略 `voice_count` 改为 `role_voice_count`，
  不再把 BGM/SE/effect 的 `z2d_req_sound` 误判为角色语音；审计 CSV 新增
  `semantic_lane`。5 个官方重捕获样本的 lane 审计位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\runtime_lane_audit_bad_samples_v1`，
  结论是 5/5 仍为 `blocked_pending_runtime_av_verification`：
  `ac4901_025/026` 为短角色语音变体，`ac7204_003` 为 gameplay/result with
  role voice，`ac0921_001` 和 `ac7204_017` 为带角色语音、需视觉语音复核的动画候选。
- v18 trust/strategy 已用新版 lane/BGM gate 重算到
  `A:\magireco_corrected_research_20260612\runtime_av_trust_audits_v18_role_lane_v4_bgm_gap_20260627`
  和
  `A:\magireco_corrected_research_20260612\pipeline_strategy_audits_v18_role_lane_v4_bgm_gap_20260627`；
  ready-missing 217 中 166 仍为可行动渲染候选、51 个继续 AV-blocked。阻断 lane：
  31 个 `audible_gameplay_result_with_role_voice`、36 个
  `blocked_short_role_voice_variant`、11 个
  `normal_animation_candidate_needs_visual_speech_review`，另有 10 个
  `pure_gameplay_or_effect_material`。新增风险
  `long_role_voice_scene_without_bgm_or_bed_audio_evidence=2`，当前命中 `ac0921_001/002`。
- 新增 `audit_render_source_integrity.py`，用于给已渲染单事件补 source hash、
  event index、累计时间轴和输出哈希复核。`ac0921_001` 审计位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\validation_outputs_runtime_repair_v1_ac0921\ac0921_001\audit`：
  event_index=2814，event_key=`MLB-8IET`，3 个输入视频、5 个输入 OGG、
  4 条字幕，`output_hash_match=true`。
- `report_pipeline_strategy.py` 现在默认把 `invalidated_do_not_use` 和
  `blocked_pending_runtime_av_verification` 从 `ready_missing_queue.csv` /
  `verification_sample_queue.csv` 剥离，写入
  `av_blocked_ready_missing_queue.csv`。重算后 217 个 ready-missing 中只有 166 个仍在
  可行动渲染候选队列，51 个被 AV gate 拦截；验证抽样队列中 AV-blocked 事件数为 0。

当前已审计可观看集合仍以 v18 输出为准：

- `A:\magireco_corrected_research_20260612\validation_outputs_v18_clean_story_ac1102_04_full`
  与 `D:\MagiReco_Reverse\magireco_verified_series_v18_clean_story_ac1102_04_20260619`；
- `A:\magireco_corrected_research_20260612\validation_outputs_v18_clean_story_ac7206_full`
  与 `D:\MagiReco_Reverse\magireco_verified_series_v18_clean_story_ac7206_20260625`；
- `A:\magireco_corrected_research_20260612\validation_outputs_v18_clean_story_ac5208_full_v2`
  作为 ac5208 追击单事件 clean story 双版本；
- `D:\MagiReco_Reverse\magireco_verified_series_v18_clean_story_ac5208_20260626`
  作为 ac5208 追击同场景 Bilibili 长片候选；
- `A:\magireco_corrected_research_20260612\validation_outputs_v18_clean_story_ac4902_full`
  作为 ac4902 clean story 单事件双版本，46/46 QA 通过；
- `D:\MagiReco_Reverse\magireco_verified_series_v18_clean_story_ac4902_20260626`
  作为 ac4902 同场景 Bilibili 长片候选，46 段、约 11分30秒、59 条字幕。
- `D:\MagiReco_Reverse\magireco_material_collections_v18_audible_20260619\ac0906`
  作为素材合集，不混入 clean story。
- `D:\MagiReco_Reverse\magireco_material_collections_v18_audible_20260626\ac0912`
  作为 small-Kyubey / CHANCE / WIN / 上乗せ 等玩法素材合集，不混入 clean story。
- 2026-06-27 素材纯度 smoke 输出位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\material_collection_purity_smoke_20260627`：
  `ac0912` 为 `pure_gameplay_or_effect_material`、`pure_material=true`、role voice=0；
  `ac7204` 为 `audible_gameplay_result_with_role_voice_not_pure_material`、
  `pure_material=false`、role voice=14，因此不得作为纯素材或 clean-story 动画。
- 以下 v18 输出已作废为“不可交付，只保留审计”：generic strategy sample、
  `validation_outputs_v18_clean_story_ac4901_full`、
  `magireco_verified_series_v18_clean_story_ac4901_20260626`、
  `validation_outputs_v18_clean_story_ac7204_full`、
  `validation_outputs_v18_clean_story_ac7204_character_subset`、
  `magireco_verified_series_v18_clean_story_ac7204_character_subset_20260626`。
  这些输出曾通过技术 QA，但未证明运行时完整 BGM/SE/voice、字幕可靠性和视觉语音一致性。
- `ac7204` material collection 仍作为玩法/结果组件审计材料保留；但其 audible review
  edition 含角色语音，应归为“gameplay/result with role voice”，不是纯素材，不得混入
  clean story 或普通动画长片。

本轮复核结果：

- `ac1102`、`ac1103`、`ac1104` 的 v18 单事件 QA 列表、production manifest ready 列表、
  以及 `D:\MagiReco_Reverse\magireco_verified_series_v18_clean_story_ac1102_04_20260619`
  中三个 series manifest 的 sources 完全一致；没有漏 ready 事件或额外混入事件；
- `ac1102/ac1103/ac1104` 三个同场景长片均为 direct stream-copy，保留 416x232、
  30/1、48 kHz 双声道，series manifest 记录 cumulative timeline、每段 SHA-256、
  合并字幕和双版本音频哈希；
- `ac0906` material collection 复核为黑幕小 Kyubey 素材层，production manifest 中
  6 个事件全部带 audience exclusion reason；material manifest 分类为
  `reviewed_audience_components_not_standalone_animation`，没有混入 clean story。

全量覆盖缺口审计已生成：

```text
A:\magireco_corrected_research_20260612\coverage_audits_v18_20260626\event_coverage_v18.csv
A:\magireco_corrected_research_20260612\coverage_audits_v18_20260626\event_coverage_v18_summary.json
```

当前覆盖状态：

- 521 个 ready events 中，304 个已有未作废的 v18 单事件 QA，217 个仍需渲染/QA；
- 521 个 ready events 中，267 个已有未作废的同场景 series/preserved 覆盖，254 个仍需长片策略；
- 405 个 audience-excluded events 中，82 个已有 material collection 覆盖，323 个仍需素材归档或
  明确仅文档排除。
- AV 信任审计当前标记 78 个事件为 `invalidated_do_not_use`，10 个事件为
  `blocked_pending_runtime_av_verification`；详见
  `A:\magireco_corrected_research_20260612\pipeline_strategy_audits_v18_20260626\av_blocked_queue.csv`。

## 2026-06-18 运行时纠偏状态

本轮停止扩散旧的错误大批量输出，改为只沿“运行时证据 -> 生产清单 ->
单事件渲染 -> QA”链路推进。

当前新增确认：

- `ac1103_013` 已通过运行时捕获证明其官方链路包含独立角色语音、
  图形字幕和多层视频合成；
- `ac1102_006` 已按静态延长审计转为 `hold_last_frame`，现在保留
  官方音频尾声而不再因 482 ms 超时被拒绝；
- `ac1104_012` 已按静态延长审计转为 `hold_last_frame`，现在保留
  官方失败音频尾声而不再因 2586 ms 超时被拒绝；
- `ac1104_014` 已确认是 `c007/c007_LP` 底层全画面加
  `c009/c009_LP` 黑底 cut-in 叠层，现已纳入正式分层 plan；
- `production_manifests_v15` 已修复两个关键回归：
  `event_audio_components.csv` 的空 `ogg_path` 现在会按 `ogg_name`
  自动回填，`exact_gdb_frame_only` 图文字幕也重新纳入正式清单；
- 新的 `production_manifests_v15` 将该事件标记为
  `verified_native_composite`，原生尺寸固定为 `416x232`；
- 渲染结果严格分离为 `with_subtitles` / `without_subtitles` / `subtitles`
  三个目录，不再混放；
- 两个版本音轨哈希一致，且实际非静音；
- 不再创建 1920x1080 画布，也不再把非证实的 UI / 图标组件混入成片。

本轮有效输出：

```text
A:\magireco_corrected_research_20260612\validation_outputs_v15_ac1103_013
A:\magireco_corrected_research_20260612\validation_outputs_v15_ac1102_family
A:\magireco_corrected_research_20260612\validation_outputs_v15_ac1104_family
A:\magireco_corrected_research_20260612\validation_outputs_v15_ac0908_food_sample
```

便于人工复核的干净集合：

```text
A:\magireco_corrected_research_20260612\validated_ac1103_runtime_set_v1
A:\magireco_corrected_research_20260612\validated_ac1103_runtime_set_v2
```

其中 `validated_ac1103_runtime_set_v2` 为当前主集合，包含 4 条同一版
`v15` 清单下通过 QA 的事件样片：

- `ac1103_005`
- `ac1103_006`
- `ac1103_012`
- `ac1103_013`

`ac1103` 全 family 的 13 条事件也已经在同一版 `v15` 清单下完成渲染和 QA：

```text
A:\magireco_corrected_research_20260612\validation_outputs_v15_ac1103_all
A:\magireco_corrected_research_20260612\validated_ac1103_full_v15
```

详细证据见：

```text
docs/research/2026-06-18-ac1103-013-runtime-composite.md
docs/research/2026-06-18-ac1102-ac1104-family-fixes.md
```

## 2026-06-12 纠错状态

旧的“按尺寸判定完整画面后直接拼接”结论已作废。当前采用
`production_manifests_v2`：

- 146 个“全画面且语音已唯一匹配”候选中，119 个通过线性时间轴检查；
- 27 个存在重叠分支、合成层或无循环依据的长时间轴，已拒绝自动成片；
- 119 个事件均生成独立的有字幕版和无字幕版；
- 两版均保持源分辨率和帧率，不创建放大画布；
- 两版音频逐事件哈希一致，且全部实际非静音；
- 最终两套 MP4 合计约 516 MB，QA 失败 0。

当前结果：

```text
A:\magireco_corrected_research_20260612\production_outputs_v2
```

完整纠错证据见：

```text
docs/research/2026-06-12-corrective-runtime-audit.md
```

`DebugDispNameList.DIR_NAME_TBL` 中的 68 个北欧神话演出名属于共用引擎或
旧机型残留，不能用于魔法纪录成片命名。当前权威命名来源是 native
`EventInfo`、GDB/Z2D/DGM 映射和运行时 `fnReqScene`。

## 审计范围

已检查本地 APK/解包内容、JADX 输出、smali、native 字符串、GDB、`m_info.dat`、`sound_id.dat` 和现有提取脚本。

JADX CLI 输出目录：

```text
jadx_audit/base_src_only
```

JADX 输出文件数：1142。

## 关键代码层结论

Java/smali 层显示：

- `SlotMainActivity` 将 `cri.bin`, `cri2.bin`, `cri3.bin` 以及对应 add 表交给 `SysMng`
- `SysMng` 调用 native `nsysmSetCriFileNames` 和 `nsysmLoadOffset`
- 演出调试入口 `DebugProd.dispatchData(int,int,int,int,int)` 也是 native
- `DebugDispNameList` 和 `DebugProd` 提供演出标签，但不包含完整视频播放/拼合逻辑

native 层显示：

- `libARES.so` 包含 `CBinCtrl`, `LoadOffset`, `GetFileOffset`, `CRI_FUSION_FILENAME`, `MARGE_INFO_FILENAME`, `OGG_FUSION_FILENAME`, `SOUND_ID_FILENAME`
- `libGameProc.so` 含大量 `acXXXX`、图像/演出/音频资源字符串
- 实际资源选择、offset 读取、融合包处理和可能的演出调度主要在 native

## 资产统计

基础清单：

| 类型 | 数量 |
| --- | ---: |
| CRID 视频 chunk | 7801 |
| 唯一视频命名 | 483 |
| 多候选视频 chunk | 607 |
| 无直接视频候选 | 6711 |
| z2d chunk | 12083 |
| z2d 名称引用 | 11733 |
| OGG chunk | 9952 |
| `sound_id.dat` 记录 | 9951 |
| 含内嵌 `@SFA` 音频的视频 slice | 456 |
| PCM chunk | 21 |
| `m_info.dat` 记录 | 1084 |

内部审计：

| 项目 | 数量 |
| --- | ---: |
| Java/smali 关键文本引用 | 516 |
| native 方法声明 | 130 |
| native 相关字符串 | 41814 |
| native `ac` token | 34441 |
| native 序列候选 | 22979 |
| 视频序列候选 | 263 |
| 高置信视频序列候选 | 175 |
| 图像 `ac` 分组 | 256 |

## 视频命名与拼合判断

当前视频命名必须保守：

- 483 个 CRID chunk 可以唯一命名
- 多候选共享 chunk 不能强行命名为单一 `acXXXX_NNN`
- `ac0902`, `ac4921`, `ac0904`, `ac3409`, `ac3410`, `ac5102` 等存在长连续编号
- 这些长序列高置信，但很多 chunk 被多个演出名共享，所以只适合进入复核队列，不适合无条件自动拼合

当前建议：

- 先导出小样本视频，按 `video_sequence_candidates.csv` 人工或脚本核验画面连续性
- 对共享 chunk 建立画面 hash/时长/分辨率/音轨一致性检查后，再进入自动合并
- 未唯一命名的视频保留 `package + index`，避免误标

## 图像分类判断

z2d 的 GDB 名称引用足够多，可以按嵌入的 `acXXXX` 分组。

仍需注意：

- 大量 unclassified 图像可能是系统 UI、通用部件或非 `ac` 前缀资源
- 不应尝试伪装成 PNG；当前只导出 raw `.z2d`

## 音频判断

`sound_id.dat` 已解析为：

- 7 字节头
- 后续 9951 条记录
- 每条 12 字节
- 包含声音资源号、OGG chunk index、bank/category、固定 marker

OGG chunk 0 未映射，可能是保留项。chunk 1 起可以用：

```text
snd_<sound_resource_id>_bank<sound_bank>_ogg_<ogg_chunk_index>.ogg
```

示例：

```text
snd_00067_bank01_ogg_00001.ogg
```

视频内嵌音频判断：

- 全部 7801 个 CRID 视频 slice 中，456 个包含 `@SFA` 音频块
- `main`：230 个包含内嵌音频，4972 个不包含
- `patch`：226 个包含内嵌音频，2373 个不包含
- `ac0902_608..627` 样本没有 `@SFA`，所以导出 MP4 没有音轨是符合原始数据的
- `main:97` 样本包含 `@SFA`，导出后 `ffprobe` 显示 `h264 + alac`，说明内嵌音频解复用流程可工作

当前需要分清两类音频：

- CRID 内嵌 `@SFA`：可以随视频一起封装进 MP4
- 外部 OGG/PCM：需要从游戏事件、sound id 或 native 调度逻辑中建立对应关系，不能直接按视频文件名自动匹配

新增 `sound-request-audit` 后，已解析 `zg_snd_request_tbl.bin`：

| 项目 | 数量 |
| --- | ---: |
| 声音表可用字符串 | 22232 |
| 声音请求行 | 11249 |
| 可连接到 `sound_id.dat` 的请求行 | 9934 |
| 带描述标签的请求行 | 8501 |
| 附近存在 `.smz/.pcm` 媒体候选的请求行 | 11203 |

重要限制：

- 声音请求表内有大量语义标签，如 `seq_共通_発展`、`結果表示_WIN`、`セリフ` 等，可用于音频分类和人工复核。
- 当前未发现 `ac0902` 这类视频编号直接出现在声音请求表中。
- `nearest_media` 只是同表邻近候选，不能直接当作视频同步关系。
- 视频和外部 OGG/PCM 的最终同步关系仍需继续审计演出调度、事件表或 native 逻辑。

## 当前可用标准

项目已经达到“可继续批处理前的审计可用标准”：

- 能生成可复现清单
- 能区分唯一命名、多候选、无候选视频
- 能解析音频 ID 映射
- 能将图像按 `acXXXX` 做初步分类
- 会默认 dry-run，降低误操作风险

尚未达到“全自动最终整理标准”：

- 视频拼合仍需共享 chunk 复核
- z2d 真实图像格式仍需专门解码器或格式解析
- 音频和视频是否存在独立同步表尚未完全确认

## RAMDISK 全量导出复核

已使用 48GB RAMDISK 完成全量导出，并备份到：

```text
D:\MagiaRe_RAMDISK_Backup_20260603_032042
```

导出结果：

| 类型 | 数量 | 状态 |
| --- | ---: | --- |
| MP4 | 7801 | `ffprobe` 失败 0 |
| 含内嵌音轨 MP4 | 456 | 与 CRID `@SFA` 扫描一致 |
| 无内嵌音轨 MP4 | 7345 | 需要外部 OGG/PCM 关联审计 |
| OGG | 9952 | `ffprobe` 失败 0 |
| PCMRAW | 21 | 0 字节文件 0 |
| Z2D raw | 12083 | 0 字节文件 0 |

新增 `video-review` 命令后，已生成：

- `asset_manifests/video_review_sequences.csv`
- `asset_manifests/video_review_items.csv`
- `asset_manifests/video_review_unique_runs.csv`
- `asset_manifests/video_review_summary.md`
- `asset_manifests/video_review_concat_plans/`

复核结论：

- 263 个视频序列候选中，261 个仍涉及共享 chunk，不能直接最终合并
- 2 个序列存在同名映射歧义：`ac3409_263`, `ac8052_001`
- `ac0902` 后半段存在 26 个唯一连续片段，可用于视觉预览
- 已在 D 盘备份目录生成 26 个 `ac0902` 预览拼合 MP4，全部可被 `ffprobe` 读取，失败 0，均无音轨
- MP4 容器审计未发现“只有音频、没有视频流”的文件；7801 个 MP4 均有视频流
- 456 个含内嵌音频的 MP4 中，三帧采样发现 2 个全黑画面片段、2 个近黑画面片段，这可能解释“像只有声音没有画面”的观察
- `ac0902_*` 唯一命名视频共 483 个，全部无内嵌音轨；预览拼合后仍无音轨是符合原始 CRID 数据的

## RAMDISK B 站全量测试

已重新输出全量 MP4 到：

```text
A:\magireco_bili_fulltest_20260603\videos
```

本轮没有启用未验证的序列合并，也没有把外部 OGG/PCM 强行混入视频。输出策略是：

- CRID 内嵌 `@SFA` 音频：随视频封装进 MP4
- 无内嵌 `@SFA` 的视频：保持无声
- 外部 OGG/PCM：仅保留声音请求与标签候选，等待后续调度关系审计

结果：

| 项目 | 数量 |
| --- | ---: |
| 输出 MP4 | 7801 |
| 输出体积 | 3572329040 字节 |
| 有视频无音轨 | 7345 |
| 有视频有音轨 | 456 |
| 纯音频/无视频 MP4 | 0 |
| 全黑采样视频 | 133 |
| 近黑采样视频 | 259 |

特殊复核目录：

```text
A:\magireco_bili_fulltest_20260603\review_special
```

其中：

- `audio_only`：0 个文件
- `blackish_video`：133 个文件
- `mostly_black_video`：259 个文件

B 站元数据候选已生成：

```text
asset_manifests/bilibili_metadata_summary.md
asset_manifests/bilibili_video_metadata_candidates.csv
asset_manifests/bilibili_sound_label_candidates.csv
```

当前可获取的投稿辅助信息包括：

- 应用正式名：`スマスロ マギアレコード 魔法少女まどか☆マギカ外伝`
- APK 版本：`versionName 1.0.0`, `versionCode 31`
- 263 个视频序列候选的时长、分辨率、音轨数量、共享 chunk 状态
- 2480 条可读声音请求标签候选
- `ac` 图像分组和示例素材名，可辅助判断故事、角色、结尾、简介、UI 场景

## 2026-06-04 增量审计

### review_special 关系确认

`review_special` 目录是复核索引，不是原视频的唯一位置。当前在 NTFS 上优先使用 hardlink：

- `review_special\blackish_video\main_video_1150.mp4` 与 `videos\Unclassified_Slices\main_video_1150.mp4` 是同一文件数据的 hardlink
- `review_special\blackish_video\main_video_0529_candidates2.mp4` 与 `videos\MultiCandidate_Slices\main_video_0529_candidates2.mp4` 是同一文件数据的 hardlink

结论：

- 没有移动原视频
- `review_special` 中的文件仍在 `videos` 分类目录中可见
- `blackish_video` / `mostly_black_video` 只是亮度采样复核列表，不是删除列表；里面包含不少合法暗色素材、卡面、边框或 UI 片段

### 音频位置确认

当前 A 盘测试结果中：

- 带内嵌音频 MP4：`A:\magireco_bili_fulltest_20260603\review_audio\with_embedded_audio`
- 外部 OGG：`A:\magireco_bili_fulltest_20260603\audio_assets\audio\ogg_raw`
- 外部 PCM：`A:\magireco_bili_fulltest_20260603\audio_assets\audio\pcm_raw`

内嵌音频统计：

| 项目 | 数量 |
| --- | ---: |
| 有视频无音轨 MP4 | 7345 |
| 有视频有音轨 MP4 | 456 |
| `MultiCandidate_Slices` 中有音轨 | 49 |
| `Unclassified_Slices` 中有音轨 | 407 |
| `ac0902_演出` 中有音轨 | 0 |

456 个内嵌音频 MP4 的音频编码是 `alac`。外部 OGG/PCM 已导出并按 `sound_id.dat` 命名，但尚未找到可证明同步到具体视频片段的调度关系。

### 候选数连续段合并测试

新增命令：

```powershell
python magireco_asset_pipeline.py merge-candidate-runs --video-dir A:\magireco_bili_fulltest_20260603\videos --out-dir A:\magireco_bili_fulltest_20260603\merge_tests\candidate_runs_command_execute_hflip_video_only --execute --hflip --drop-audio --probe
```

规则：

- 只处理 `MultiCandidate_Slices`
- 文件名需匹配 `main_video_NNNN_candidatesX.mp4` 或 `patch_video_NNNN_candidatesX.mp4`
- 按 `package + index` 排序
- 仅当 index 连续且 `candidatesX` 相同时合并
- 单片仍输出一份，便于形成完整复核目录
- 本次执行使用 `--hflip --drop-audio`，因此输出为水平翻转校正后的 video-only 测试结果

结果：

| 项目 | 数量 |
| --- | ---: |
| 原 `MultiCandidate_Slices` MP4 | 607 |
| 输出 MP4 | 73 |
| 真正合并段 | 29 |
| 单片保留 | 44 |
| 执行失败 | 0 |

示例：

```text
main_video_0071-0099_candidates24.mp4
```

该文件来自 29 个源片段，时长 48.100 秒，源片段中 3 个带内嵌音频；当前测试输出故意去掉音频，避免混合“有音轨/无音轨”片段时产生错误合并。

### 镜像方向问题

用户复核确认当前导出视频存在左右镜像问题。本轮生成了方向样张：

```text
A:\magireco_bili_fulltest_20260603\orientation_check
```

候选数合并测试输出已使用 `hflip` 做水平翻转校正。原 `videos` 全量目录未被改写。

### 安装态拉取与完整性

通过 MuMu / adb root 拉取安装态内容到：

```text
A:\magireco_installed_pull_20260603
```

拉取结果：

| 目录 | 文件数 | 字节 |
| --- | ---: | ---: |
| `data_app_package` | 11 | 832841272 |
| `data_user_0` | 16 | 154288355 |
| `sdcard_Android_data` | 5 | 6158460910 |
| `sdcard_Android_obb` | 0 | 0 |

完整性判断：

- 安装态 6 个 APK/split APK 与项目目录本地 APK/split APK 的 SHA256 全部一致
- 安装态 `main.9...obb` 与 `patch.9...obb` 与本地 `downloaded_assets` 版本 SHA256 一致
- 因此现有 APK/JADX/apktool 输入和 Python 复刻下载得到的 OBB 主资源没有发现缺失或偏差

新增有价值内容：

```text
A:\magireco_installed_pull_20260603\data_user_0\files\assetpacks\OnDemandPack01\31\31\assets\smz.bin
A:\magireco_installed_pull_20260603\data_user_0\files\assetpacks\OnDemandPack01\31\31\assets\smz_add.bin
```

`smz_add.bin` 是 `smz.bin` 的 32-bit 小端偏移表，共 9753 个偏移，定义 9752 个资源块。2026-06-05 的增量审计修正了初步判断：它更可能是声音媒体容器，不是优先的图像/模型容器。

## 2026-06-05 声音媒体与 SMZ 增量审计

新增命令：

```powershell
python magireco_asset_pipeline.py sound-media-audit --smz-bin A:\magireco_installed_pull_20260603\data_user_0\files\assetpacks\OnDemandPack01\31\31\assets\smz.bin --smz-add A:\magireco_installed_pull_20260603\data_user_0\files\assetpacks\OnDemandPack01\31\31\assets\smz_add.bin
```

输出：

```text
asset_manifests/sound_hashreq_records.csv
asset_manifests/smz_chunk_header_audit.csv
asset_manifests/smz_name_chunk_map.csv
asset_manifests/smz_request_missing_from_installed_pack.csv
asset_manifests/pcm_name_table.csv
asset_manifests/sound_media_summary.md
```

关键结果：

| 项目 | 数量 |
| --- | ---: |
| 结构化 ReqData 唯一 SMZ 媒体名 | 9758 |
| 结构化 ReqData SMZ 引用 | 10944 |
| 结构化 ReqData 唯一 PCM 媒体名 | 21 |
| 结构化 ReqData PCM 引用 | 21 |
| `zg_snd_hashreq_tbl.bin` 记录 | 10420 |
| 通过记录序号关联到结构化 request 的 hash 行 | 10420 |
| 非零 `sample_count_u32` 行 | 9936 |
| 安装态 `smz.bin` chunk | 9752 |
| `loadFileSmz` relocated 名称 | 9752 |
| request 表中存在且安装态存在的 SMZ 名称 | 9752 |
| request 表有但安装态表无的 SMZ 名称 | 6 |
| 安装态有但 request 表未引用的 SMZ 名称 | 0 |
| `loadFilePcm` relocated 名称 | 21 |
| request 表中存在且安装态存在的 PCM 名称 | 21 |
| 推测 mono chunk | 6826 |
| 推测 stereo chunk | 2926 |

判断：

- `DecoderSmz::open_stream()` 使用 `loadFileSmz` 名称表查找媒体 basename，再使用 `g_SMZDataAddress[i]..[i+1]` 从 `smz.bin` 取 chunk；官方 SMZ 名称到 chunk 序号的映射已经可以生成。
- `SndInitManager()` 会把 `smz_add.bin` 读入 `g_SMZDataAddress`，把 `pcm_add.bin` 读入 `g_PCMDataAddress`。
- `zg_snd_hashreq_tbl.bin` 是 `64 + 10420 * 16` 字节；记录按 request index 对齐，结构为 `8-byte hash + sample_count_u32 + zero tail`。旧判断里的第三个字段不是 request id。
- 抽样切出的 `.smz` chunk 不能直接被 `ffprobe` 或简单跳过 header 的 MP3 探测识别；后续仍需要复用/还原游戏内 `DecoderSmz` 解码器，或做运行态音频捕获。
- 这次审计解决了“官方 SMZ 媒体名 -> 安装态 chunk”的地图，但仍没有证明外部声音与具体视频片段的同步关系。

对 B 站最终整理的影响：

- 已确认 456 个 MP4 本身带内嵌音轨，可优先作为有声候选。
- 7345 个无内嵌音轨 MP4 不能直接按 `.smz`、OGG 或 request id 强行配音。
- 可先用声音请求标签筛选投稿标题、说明和人工复核候选，例如 `魔法少女変身`、`マギア`、`ストーリー`、`WIN`、角色名等。

### Native 声音/视频字符串证据

新增命令：

```powershell
python magireco_asset_pipeline.py native-sound-video-audit
```

输出：

```text
asset_manifests/native_sound_video_evidence.csv
asset_manifests/native_sound_video_summary.md
```

结果：

| 类别 | 数量 |
| --- | ---: |
| `sound_media_table` | 6 |
| `sound_request_symbol` | 16 |
| `event_label` | 588 |
| `ac_play_method` | 15 |

关键证据：

- `smz.bin`, `smz_add.bin`, `zg_snd_hashreq_tbl.bin`, `sound_id.dat`, `ogg.bin`, `ogg_add.bin` 均出现在 native 字符串证据中。
- Java/smali 只暴露 `SndMng.nsmSndReq(int)` 入口，真正的声音请求路由仍在 native。
- `ac5406`, `ac5407`, `ac5408` 有专用 `fnSndRequest_BGM` native 符号，并且有 `EVT_ac` 标签。
- `ac1101` 至 `ac1206` 以及 `ac5209` 出现在 `C_ObjNml::fnSndRequest_BGM_DIR()` 证据中。
- `ac5102` 有 45 条 `EVT_ac` 标签，但当前字符串级审计没有看到直接 `sound_request_symbol`。
- `ac0902`, `ac4921`, `ac0904`, `ac3409`, `ac3410` 当前没有直接字符串级声音请求或 `EVT_ac` 证据。

判断：

- 该结果支持“视频/演出和声音存在 native 事件层关联”的方向。
- 但它仍是字符串级证据，不是最终同步表；不能据此自动把 OGG/SMZ 合并到 `ac0902` 或其他视频。

### ac5408 反汇编样本

本机没有现成 `objdump/readelf`，因此本轮使用纯 Python 解析 ELF `.dynsym`，并临时将 Capstone 安装到 `A:\TEMP\pydeps_capstone` 做只读反汇编。

关键函数地址：

| 函数 | 地址 | 大小 | 判断 |
| --- | ---: | ---: | --- |
| `C_ac5406::fnSndRequest_BGM()` | `0x43e9eb4` | 4 | 只有 `ret` |
| `C_ac5407::fnSndRequest_BGM()` | `0x43ea9e8` | 4 | 只有 `ret` |
| `C_ac5408::fnSndRequest_BGM()` | `0x43ec088` | 88 | 有实际逻辑 |

`ac5408` 相关函数中反汇编出的数字字符串：

| 来源函数 | 数字字符串 |
| --- | --- |
| `fnSndRequest_BGM` | `9078` |
| `fnPlaySND` | `296`, `283`, `6825`, `26497`, `6830`, `8032`, `1053`, `1052`, `1051`, `1050`, `1049` |

这些数字大多可以作为 `sound_resource_id` 映射到 OGG，但部分也能作为 `ogg_chunk_index` 映射到另一个声音资源。例如 `9078` 作为 request id 没有 OGG 映射，但作为 OGG chunk index 对应 `snd_04718_bank03_ogg_09078.ogg`。因此当前不能只按数字文本直接合并音频，必须继续确认调用函数语义。

PLT 解析后已确认关键调用语义：

| PLT 地址 | 符号 | 作用判断 |
| --- | --- | --- |
| `0x449ca00` | `_Z10CTRLSNDLIBv` | 获取声音控制库对象 |
| `0x449d5e0` | `C_CtrlSndLib::fnReqSndSoundCode(char const*, unsigned char)` | 按字符串声音代码请求声音 |
| `0x4492820` | `C_AnmBase::fnGetCallSignFlag(unsigned short)` | 演出标志判断 |

因此 `ac5408` 中的 `9078`, `296`, `283`, `6825`, `26497`, `6830`, `8032`, `1049-1053` 应优先解释为 `fnReqSndSoundCode` 的声音代码字符串，而不是 OGG chunk index。`9078` 虽然作为 OGG index 能落到 `snd_04718_bank03_ogg_09078.ogg`，但该解释目前低优先级。

进一步追踪已确认完整派发链：

```text
fnReqSndSoundCode -> fnSendSndData -> SndReceiveMessage(0x201)
  -> SndMngSetRequest -> SndMngFrameFunction -> zgSndReqCode -> zgSndReqId
```

这说明 `ac5408` 的数字字符串是官方声音代码输入。继续解析 `RequestCtrl::loadRequestTbl()` 后确认：code string 会映射到 `zg_snd_request_tbl.bin` 中的 request index，不等于 `sound_id.dat` 的 `sound_resource_id`。因此早期按 `sound_resource_id == code` 复制 OGG 的 `A:\magireco_bili_fulltest_20260603\sound_code_tests\ac5408_official_code_candidates` 已降级为低置信度参考。

新的结构化候选包位于：

```text
A:\magireco_bili_fulltest_20260603\sound_code_tests\ac5408_structured_code_to_smz
```

重点 code 的官方映射示例：

| code | request_id | first SMZ |
| --- | ---: | --- |
| `9078` | 2074 | `2A40747716A2B334129B4E859D42.smz` |
| `1049` | 444 | `F53FACA2830323AB642C1AD01802.smz` |
| `1050` | 445 | `83D6634F254D3A407E8028CC1732.smz` |
| `1051` | 446 | `22F05E94C422EDECF73A66E214B2.smz` |
| `1052` | 447 | `B91EA87EC141173B3EF70D8B4052.smz` |
| `1053` | 448 | `8A4A233E6BB8CFB14C79E1F234F2.smz` |
| `6825` | 1492 | `1622D09E2ADD3F9E609DCF959772.smz` |
| `6830` | 1497 | `37288F4F4F95C8C8146FA2035B22.smz` |
| `8032` | 1678 | `6C42AA7341BB599291C9B7D35312.smz` |
| `26497` | 8297 | `219AB8B97C4E29291BB44B4EFBB2.smz` |

### D 盘归档

本轮新增内容已复制到：

```text
D:\MagiaRe_RAMDISK_Delta_20260604_002343
```

归档内容包括：

- 候选数合并测试输出与 manifest
- 方向样张
- 带内嵌音频 MP4 复核集合
- `review_special` 复核目录
- `OnDemandPack01` 和小型运行态文件

没有重复归档全量 MP4、raw OGG/PCM、APK、OBB；这些已在旧 D 盘备份或本地工程中存在，且哈希/数量/总大小已验证一致。

## 2026-06-05 RAMDISK 修正状态

### 方向修正

用户人工确认原始全量目录仍是左右反向，包括：

```text
A:\magireco_bili_fulltest_20260603\videos
A:\magireco_bili_fulltest_20260603\review_special
A:\magireco_bili_fulltest_20260603\review_audio\with_embedded_audio
```

已新增 `hflip-videos` 命令，并在 A 盘生成方向正确的全量输出：

```text
A:\magireco_bili_fulltest_20260603\videos_hflip
```

执行结果：

| 项目 | 数量 |
| --- | ---: |
| 输入 MP4 | 7801 |
| NVENC 首轮成功 | 7031 |
| NVENC 因小尺寸失败 | 770 |
| libx264 补跑成功 | 770 |
| 最终 MP4 | 7801 |
| 0 字节输出 | 0 |

说明：

- 原始 `videos` 未移动、未覆盖。
- `videos_hflip` 是当前后续复核和投稿整理应使用的视频树。
- `hflip_manifest_nvenc_firstpass.csv` 保留了首轮 NVENC 失败证据；当前 `hflip_manifest.csv` 是 libx264 补跑结果。

### 内嵌音轨不等于可听声音

用户指出 `review_audio\with_embedded_audio` 中部分文件实际无声。已用 `ffmpeg volumedetect` 复核，确认旧分类只表示“MP4 容器有音频流”，不表示“有可听声音”。

关键样本：

| 文件 | 音频流 | mean_volume | max_volume | 判断 |
| --- | --- | ---: | ---: | --- |
| `Unclassified_Slices\main_video_2243.mp4` | `alac` | -91.0 dB | -91.0 dB | 静音音轨 |
| `Unclassified_Slices\patch_video_1343.mp4` | `alac` | -91.0 dB | -91.0 dB | 静音音轨 |
| `MultiCandidate_Slices\main_video_0097_candidates24.mp4` | `alac` | -10.3 dB | 0.0 dB | 可听音轨 |

已对方向正确的 `videos_hflip` 重新生成复核目录：

```text
A:\magireco_bili_fulltest_20260603\review_special_hflip_audible
```

结果：

| 类别 | 数量 |
| --- | ---: |
| normal | 7096 |
| silent_audio_track | 315 |
| mostly_black_video | 259 |
| blackish_video | 131 |
| audio_only | 0 |
| no_video_stream | 0 |
| probe_failed | 0 |

音频响度统计：

| audible_audio | 数量 |
| --- | ---: |
| yes | 141 |
| no | 315 |
| 空值/无音轨 | 7345 |

已单独硬链接出 141 个方向正确且真正有可听内嵌音频的视频：

```text
A:\magireco_bili_fulltest_20260603\review_audio_hflip\audible_embedded_audio
A:\magireco_bili_fulltest_20260603\review_audio_hflip\audible_embedded_audio_manifest.csv
```

### PCMRAW 转 WAV

`pcm_raw` 下的 21 个 `.pcmraw` 不能被 foobar2000 直接播放，因为它们不是 WAV 容器。探测结果显示每个文件是：

```text
32 字节自定义头 + s16le PCM payload
```

其中第一个 little-endian `u32` 等于 `文件长度 - 32`。

已新增 `convert-pcm-wav` 命令，并输出可播放 WAV：

```text
A:\magireco_bili_fulltest_20260603\audio_assets\audio\pcm_wav_48k_stereo
```

当前采用：

```text
s16le, 48000 Hz, stereo, skip 32 bytes
```

结果：

| 项目 | 数量 |
| --- | ---: |
| PCMRAW 输入 | 21 |
| WAV 输出成功 | 21 |
| 可听 WAV | 20 |
| 静音 WAV | 1 |

静音样本：

```text
pcm_00018.wav
```

### 安装态拉取价值

`A:\magireco_installed_pull_20260603` 已检查。相对旧 APK/下载包，最有价值的新增证据是安装态 Play Asset Delivery 目录：

```text
A:\magireco_installed_pull_20260603\data_user_0\files\assetpacks\OnDemandPack01\31\31\assets\smz.bin
A:\magireco_installed_pull_20260603\data_user_0\files\assetpacks\OnDemandPack01\31\31\assets\smz_add.bin
```

这些文件不在当前工程的 `unpacked_assets\assets` 常规资源目录中，必须保留用于 SMZ 声音研究。

当前哈希：

| 文件 | SHA256 |
| --- | --- |
| `smz.bin` | `AFBA721F0677DB90945711484D807C224250EDFA7E2945C4D1049B36777B501C` |
| `smz_add.bin` | `EAB5C3DE37CBCB8AD437106AC319EAB67D7DB5A65457177195D15B4D4ADA7F82` |

重新用安装态 `smz.bin/smz_add.bin` 执行 `sound-media-audit` 后确认：

| 项目 | 数量 |
| --- | ---: |
| runtime SMZ chunks | 9752 |
| runtime SMZ mono guess | 6826 |
| runtime SMZ stereo guess | 2926 |
| request 表有且安装态存在的 SMZ 名称 | 9752 |
| request 表有但安装态缺失的 SMZ 名称 | 6 |
| runtime SMZ 未被 request 表引用 | 0 |
| runtime PCM 名称 | 21 |
| request PCM 缺失 | 0 |

`sdcard_Android_data\files` 中的 OBB 与项目已有 OBB 尺寸一致；`gameData.bin/configData.bin/pad.bin` 目前只发现安装路径、访问状态和小型运行状态信息，没有发现新的演出命名或视频同步表。

### 本阶段 D 盘归档

已将本阶段 RAMDISK 研究成果固实压缩到：

```text
D:\MagiReco_Reverse\MagiaRe_RAMDISK_Research_20260605_hflip_audio_installed_pull.7z
```

归档范围：

```text
A:\magireco_bili_fulltest_20260603
A:\magireco_installed_pull_20260603
A:\timelines
```

未纳入归档：

- A 盘系统目录
- `A:\TEMP`
- Frida 临时下载/解压二进制
- 0 字节 `gamerecording.pb`

7-Zip 校验结果：

| 项目 | 数值 |
| --- | ---: |
| Folders | 86 |
| Files | 27904 |
| 原始大小 | 16163305230 bytes |
| 压缩大小 | 13731737346 bytes |
| `7z t` | Everything is Ok |

## 2026-06-05 运动审计与字幕候选

### 极短/静止视频审计

新增命令：

```powershell
python magireco_asset_pipeline.py motion-audit --video-dir A:\magireco_bili_fulltest_20260603\videos_hflip --out-dir A:\magireco_bili_fulltest_20260603\motion_audit_videos_hflip --collect-review --workers 4
```

全量方向正确视频树结果：

| 类别 | 数量 |
| --- | ---: |
| normal_motion | 2671 |
| very_short | 2371 |
| short | 1530 |
| low_motion | 490 |
| short_static | 426 |
| static_like | 313 |

真正可听内嵌音轨的 141 个视频结果：

| 类别 | 数量 |
| --- | ---: |
| normal_motion | 93 |
| short | 17 |
| low_motion | 16 |
| static_like | 8 |
| very_short | 4 |
| short_static | 3 |

关键判断：

- 大量 1 秒以内视频、短静止视频是游戏素材/分支/触发资源形态，不是导出脚本单点失败。
- `main_video_0294_candidates4.mp4` 和 `main_video_0303_candidates4.mp4` 有音轨但极短且低运动，人工听感接近无声是合理的。
- `patch_video_1199.mp4` 和 `patch_video_1205.mp4` 属于正常运动长片段；上下镜像更像场景内反射构图，不是需要修正的整体方向问题。

当前审查目录：

```text
A:\magireco_bili_fulltest_20260603\motion_audit_audible_embedded
A:\magireco_bili_fulltest_20260603\motion_audit_videos_hflip
```

### 字幕/台词候选

新增命令：

```powershell
python magireco_asset_pipeline.py subtitle-candidates
```

输出：

```text
asset_manifests\subtitle_dialogue_candidates.csv
asset_manifests\subtitle_dialogue_candidates_summary.md
```

严格台词候选：

| 项目 | 数量 |
| --- | ---: |
| 台词行 | 896 |
| 可连接 runtime SMZ | 896 |
| 可连接 OGG 命名 | 886 |
| 解析出 `subtitle_text` | 877 |

判断：

- 项目已经能提取大量官方台词标签，可作为字幕版文本初稿。
- 这些不是 timed subtitles；最终字幕还需要事件时间轴、SMZ/OGG 解码时长或人工对齐。
- 原始标签存在截断，不能把 `subtitle_text` 直接视为完整官方台本。

### SMZ 状态修正

`DecoderSmz` native 符号包含 `frame_get_side_info`、`frame_get_scale_factors`、`frame_dequantize_sample`、`dct36/dct64`、`decode_frame`、`openForConvert` 等 MP3 Layer III 风格流程。

当前判断：

- SMZ 不是简单“跳过 header 后交给 ffmpeg”的容器。
- chunk 前 32 字节为自定义头，后续没有标准 MPEG frame sync。
- 官方解码优先路线仍是调用游戏自身 `zgSndCaptureConvertWav*`；MuMu x86_64 + arm64 native bridge 环境下 Frida 仍不稳定。
- 静态路线需要还原 `DecoderSmz::openForConvert/read_frame/decode_frame`，成本高于简单解包。

### 本轮归档

已重新归档包含运动审计和字幕候选的 A 盘研究目录：

```text
D:\MagiReco_Reverse\MagiaRe_RAMDISK_Research_20260605_motion_subtitle.7z
```

校验结果：

| 项目 | 数值 |
| --- | ---: |
| Folders | 118 |
| Files | 31543 |
| 原始大小 | 16639306919 bytes |
| 压缩大小 | 14999419536 bytes |
| Solid | yes |
| `7z t` | Everything is Ok |
