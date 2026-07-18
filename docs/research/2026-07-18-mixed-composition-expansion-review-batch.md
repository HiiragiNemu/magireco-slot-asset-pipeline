# 2026-07-18 非线性／多层剧情首轮扩产审查批次

## 所有者授权与检查点

项目所有者完整播放 `ac7114`、`ac7115`、`ac7116` 三部章节后确认：

```text
这三部完整章节都通过，允许全面生产，不过我希望尽快将生产内容覆盖到单全画面线性 SP Story之外的视频
```

原话与三部已审 MP4/SRT/manifest/QA/READY 的 SHA-256 已绑定到：

```text
tools/frida_runtime_probe/owner_attestations/sp_story_3_5_full_chapters_owner_playback_20260718.json
```

该批准关闭了完整 Story 3/4/5 的人工播放门禁，并授权全面扩产；它不自动批准尚未
渲染的 family、`with_bgm` 版或上传行为。为验证扩产是否可以跨过“单全画面线性
SP Story”边界，本轮先生产四部结构差异明显的剧情长片。自动 QA 通过后停止，等待
项目所有者播放；未继续启动其余 family、素材集合或 BGM 捕获。

## 通用化内容

`tools/frida_runtime_probe/build_sp_story_chapter_reviews.py` 现已从固定三个 SP family
构建器扩展成 reviewed story family 构建器：

- 可为每个 family 显式指定一个已经 passed 的 series manifest；
- 支持原生 `416x232` 与 `512x288`，并按尺寸选择独立、哈希绑定的字幕布局 profile；
- 支持 `linear_full_frame_sequence` 与 `timed_full_frame_layers`；
- 线性事件可确定性投影多个按时间排序的全画面 clip，不再假设每 event 只有一个 clip；
- 保留并核验 authored timed composition 中的 background、loop background、screen overlay、
  loop screen overlay、缩放和 blend 语义；
- 支持 `none`、`hold_last_frame`、`loop_last_clip`、`composition_plan_loops` 与
  `black_tail` 的已声明扩展策略；
- voice 只按 subtitle-bound request ID 识别；`event_audio_component` 保留为 scene SE，
  其他未绑定声音显式标为 `unsubtitled_audio`，不再凭名字猜 voice；
- 中文翻译表改为可跨 family 的对白映射，仍要求完整且唯一覆盖本批所有可听日文 cue；
- 835/836 BGM 与 1681 金带声音继续失败关闭，不因扩产放宽。

真实媒体暴露并关闭了两个 CFR 边界：

1. `ac1102_003` 的 `_LP` 尾段若按浮点秒截取会多出一帧。现在先探测已拼基础帧数，
   再以 manifest 的 `render_frame_count` 分配精确循环帧预算，最终仍逐帧验证。
2. `ac1103_006` 的多层视觉计划为 11.967 秒，但经验证的声音尾端把 presentation grid
   延长到 12.933 秒。FFmpeg 多输入 framesync 在边界少产一帧；现在 timed composite
   最终先补最多两个 clone frame，再按 `end_frame` 精确裁到目标帧数。若仍短于目标，
   逐帧 QA 继续失败关闭，不能用这一操作掩盖实质缺帧。

断点续跑的复用门禁也已补齐：已有 clean visual 只有在 report 所绑定的 prepared
manifest 绝对路径与 SHA-256、输出路径与输出 SHA-256 全部等于当前输入时才可复用；
不一致时要求 `--overwrite`，而 `--overwrite` 现在会真实重渲染，不再静默跳过旧视觉。

## 全库结构盘点

权威 v20 基线仍为 926 event：521 technical READY、405 fail-closed。521 项 READY 中：

- 449 项 `linear_full_frame_sequence`；
- 72 项 `timed_full_frame_layers`；
- 368 项为 416x232，152 项为 512x288，1 项为 512x416。

仓库已有 155 个 composition plan，其中 114 个是 timed，41 个是 linear。因此全面生产
不能只重复 SP Story 单 clip 流程；本批四部同时覆盖 19 个 timed event 和 21 个 linear
event，作为进入其余 reviewed story family 前的机制检查点。

## 耐久输出与统计

批次根：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\bilibili_mixed_composition_reviews_v22_20260718
```

| family | event | linear / timed | cue | audio layer | duration | native media | video SHA-256 |
|---|---:|---:|---:|---:|---:|---|---|
| `ac1102` | 11 | 7 / 4 | 26 | 39 | 91.800 s | 416x232, 30/1 | `F2236AC4B3235C645E7408539E37AF2422077D8300C9EED2339CE73E15561BD2` |
| `ac1103` | 13 | 6 / 7 | 33 | 59 | 103.800 s | 416x232, 30/1 | `C1789C88415FEE6F52A4702B62A2F79ABB5877BAC55BE4681F56E27AC2BE5B1C` |
| `ac1104` | 13 | 8 / 5 | 33 | 54 | 100.067 s | 416x232, 30/1 | `44CB183FE70CB384995582453D76F06F2CEFD95216D888245566D961AAA51053` |
| `ac5208` | 3 | 0 / 3 | 7 | 23 | 19.400 s | 512x288, 30/1 | `55875D4C661B2A6A5FEC077A2D3235C04AF98DC264DA104A2258C29E7392626D` |

合计 40 event、99 条 voice-bound 中文字幕、175 个声音层、19 个 timed composite、
21 个 linear event 和 315.067 秒。所有 MP4 为 H.264 原生尺寸、30/1 fps；音频为
AAC 48 kHz stereo；`bgm_policy=intentionally_excluded`；未 upscale、未自动插入黑场。

关键 hash：

| family | SRT | chapter manifest | automated QA | READY |
|---|---|---|---|---|
| `ac1102` | `F409AADFC07287C1DD54D4465F234515A41F7A79C3C0E2BA193E8732CB739E0C` | `92B3A62ECCC0A695C4D61B994C9DBD94B750E57C84E1F566B0E6C5E67461FD4E` | `2754876A7AC5FAE612395E4034E58E310056197231BA769E0881E58A7B5C8CB5` | `0889A77D450D2E8C30A7CB6070077F70FD219C5F3D0A06A2DFF88B74D7289716` |
| `ac1103` | `71023863EC3C4741438926BC08B541C607C4545C403C04B434AB2B70BBAA98C9` | `F4E561EAE0A01F2277E7BA9592318DE03B0F9117364B9499BD601B3837827C05` | `EF313EB644E2EB3A1D7082F9AD391AA10977AB29CCBC65614024E26236AE024E` | `39608C5E68C9D38500377B11088B60991E8FD17904A56116B55A417028850506` |
| `ac1104` | `BB46E2CFE9431626879FA5E7713810C4A66A12C032B94AECB28C8CF90F0C89E8` | `009D2529977CBDD62507345276BFE578D24118485C94889578CC0BB1BF413F50` | `D653B3FC8E5EB8E18EB7F6714AB45B0B1FBDFF67335A3D6A9CD3CB1D5B91781D` | `06BFA7AC45F1B8DA51834B056CE4A361DD73802691B9EA492414C12811D394D0` |
| `ac5208` | `1C674A946CC9EBB1F34D68E1233484793D30A44F2992EB5828C8F85ACA0CC706` | `AA9F616D93B7D0235213D37662464D77E024BF909A19A3C7EDC0CC7DF57EA1CA` | `42B0F233BECD3D32457C5754FB4407D8AD496016214C04E84581E7B652A1DF74` | `48D760286FDFED2A8B5E622C780F54A57A90B36B0B14A32BF20DC366886EFA8E` |

`BATCH_SUMMARY.json` SHA-256：
`784669F1D5D06EFA49330AC156E45A02B98826FD7E3AA709FB5315A5B0692649`。

## 自动验证与人工边界

四部均为 `AUTOMATED_QA_PASSED`；本轮真实构建逐 event 重新验证 source hash、显式
composition、原生尺寸/帧率、精确帧数与音频样本、voice/SE 来源、BGM 排除、字幕
cue 回读、单次 AAC 编码和发布事务。全仓回归为 319 tests passed、4 skipped、
0 failed/error；skips 是环境条件测试，不是本批媒体门禁。

自动 QA 只能证明媒体合同和时间轴，不能替代语义观看。本批特别需要人工确认：

- `ac1103` 等 authored plan 中的胜利 sparkle/logo 是否属于应保留的剧情画面，还是应
  从 Bilibili clean-story 版拆到玩法／效果合集；
- `ac5208` 存在同一时段多角色发声和多条中文字幕，重叠 cue 是否可读；
- 416x232 新布局的字号、描边和遮挡是否可接受；
- voice、SE、事件边界、循环和画面层是否与内容匹配，是否意外含 BGM。

每个 family 需要完整播放：

```text
<family>_full_no_bgm_zh_review_v1\video\<family>_full_no_bgm_zh_review_v1.mp4
```

并参考同目录：

```text
review\HUMAN_PLAYBACK_REVIEW.md
review\layout_frames\*.png
```

当前四部保持 `HUMAN_PLAYBACK_APPROVED=false`、`BILIBILI_RELEASE_READY=false`。
收到项目所有者反馈前停止。若四部通过，可把同合同扩到已经 passed 且 v20-ready 的
`ac0915`、`ac4903`、`ac5203`、`ac6005`、`ac7205` 等 reviewed story family，再将
不同语义类别分批扩产；若某类不通过，只修对应 composition/分类合同，不回退已经通过
的单全画面 SP Story 流程。
