# 2026-07-18 SP Story 完整章节首轮扩产审查批次

## 所有者授权与本轮停止边界

项目所有者确认首个 44.867 秒 `ac7114_001 -> ac7115_001 -> ac7116_001`
候选“状态良好，可以继续生产更多视频”。仓库用 hash-bound attestation 保存该原话与
批准边界：

```text
tools/frida_runtime_probe/owner_attestations/ac7114_16_sp_story_no_bgm_zh_v1_owner_playback_20260718.json
SHA-256 D0CDCA3AE11BC20E68A5EB700E42C73E354B722C08CEC35D5650627FF845C022
```

该陈述证明首个候选整体播放通过并授权扩产，不冒充逐 cue 翻译批准、逐项 checklist
签署或投稿授权。

为判断能否从单一样片进入全面生产，本轮没有立即渲染 926 项，而是把同一 SP Story
机制扩大到 Story 3、4、5 三个完整 family。它们覆盖 34 个 event、107 条有声对白、
144 个 voice/scene-SE 层和 8 分 36.933 秒连续画面，显著强于只验证三个开场 event。
三部候选自动 QA 完成后停止，等待项目所有者完整播放；未启动 Story 1/2/6、其他
family、素材集合或 BGM 捕获。

## 构建合同

新工具：

```text
tools/frida_runtime_probe/build_sp_story_chapter_reviews.py
```

固定合同如下：

- 事件顺序只读取既有 passed family series manifest，不按文件名数字重新猜测；
- 每个 event 从 v20 technical-ready production manifest 复制并绑定真实来源 SHA-256；
- 旧 plan 只有表头而缺少 `clips` 时，只允许对恰好一个、从 0 开始、512x288、30 fps
  的全画面 clip 生成显式线性 projection；
- 每个 event 重新生成 clean visual；无 upscale、无自动黑场、无金框/粒子/老虎机前景；
- request 835、836（BGM）及 1681（金带声音）失败关闭；每个 event 必须恰有一个经
  业务身份识别的 scene SE，其余有声层保留为 voice；
- 只为带 `voice_request_id` 的对白生成中文字幕；无声 `graphical-only` 的
  `ごめんね…` 被排除；
- 每 event 按 v20 的 CFR frame/audio-sample grid 构造连续 48 kHz stereo PCM；全章
  只编码一次 AAC，最终 MP4 copy 该 AAC packet；
- clean visual 无重编码拼接为章节母版，中文字幕按固定 Noto Sans CJK profile 烧录；
- 构建前后 source rehash，整 family staging/READY 事务发布，失败保留旧完整输出；
- 所有人审/投稿状态固定为 false，Codex 不代替项目所有者批准。

`ac7116_003` 暴露一个 MP4 metadata 边界：437 帧的精确 presentation grid 是
`437/30 = 14.566666...` 秒，但 FFmpeg 写出的 stream/container metadata 为
14.566016 秒，整数毫秒分别为 14567 与 14566。renderer 现在只允许 1 ms metadata
取整窗口；随后仍逐帧、逐 packet 验证 437 帧、30/1 CFR、连续 PTS/DTS 和每 packet
`1/30` 秒。两毫秒差异仍失败关闭，因此没有放宽精确时间轴门禁。

## 耐久输出与统计

批次根：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\bilibili_expansion_reviews_v21_sp_story_20260718
```

| family | event | cue | audio layer | frames | duration | video SHA-256 |
|---|---:|---:|---:|---:|---:|---|
| `ac7114` Story 3 | 12 | 35 | 47 | 5230 | 174.333 s | `9FD511B3E8171D3A13EC0A02D94ED82398024AB7DC46ADE2B4E3E67ED49278A2` |
| `ac7115` Story 4 | 9 | 34 | 46 | 4641 | 154.700 s | `15F9920065FBDEE048229D7C289C9046FAEED7DA1B7E83FC0B8B6338FF2E82E5` |
| `ac7116` Story 5 | 13 | 38 | 51 | 5637 | 187.900 s | `11128187D65D4CBA00B88EDE556D19602495E3E87BBE4CE389BA87BF2FCC35FA` |

合计 34 event、107 cue、144 audio layer、15,508 帧、24,812,800 个 presentation
samples、516.933 秒。三部均为 512x288、30/1 fps、H.264；AAC 48 kHz stereo；
`bgm_policy=intentionally_excluded`；`publishable=false`。

其余关键 hash：

| family | SRT | chapter manifest | automated QA | READY |
|---|---|---|---|---|
| `ac7114` | `42AF0C9DB07453A69E195E7374BFE9C82D82296B9B4A6811F88CFE419B61FE21` | `411A403A528382F87F8264D7EC3137B242F1F76485544A71746D4D4E0E1DA622` | `D121E7CB34367A76BF52D307F3F38755950044A0C309C1E89F3D60B6997F2EB0` | `CDA8F270B52646DCC5AC99507EA1B85272D6246D0FE376FBE824359C2491764B` |
| `ac7115` | `26322EB2FCCD24E85E475AB75F2CA011B55CCAD0093C2074F445FE641348BEBF` | `FD6733F33F9810D5E51F11D8B4FFB0AEDA66AF71E7AC571C501827FA7E283DD6` | `1A80C2212326E65DC0E429BFE4D119BE9FA9106DF61F98F908BDB5A8B4E4EFD1` | `D2E9081654942E00E8148B611940A924AA250ACFA9471A73512E850E1B6B998E` |
| `ac7116` | `E0F71ACF50D718D728119885D12DCD6BD02B84B2FF54E35414245D8DF0964528` | `9EEDA59F176789DDAF898582C251FA732C92F575178058467D116A0AB37A0863` | `6E19566928393CB79AC67875EF508E11B4219206F2C5490AD1ACD111CFCA3926` | `5DCE0D19B676984A90CD81F40AB2E93316B5B8CA4040257C5F4A995819AFD260` |

`BATCH_SUMMARY.json` SHA-256 为
`71E539176649077D49F097540344157FF848622539D0FDB9EFF37D5CB9757F2B`。
所有 marker 所列 MP4/SRT/QA/review/manifest hash 已从发布目录重新计算并完全匹配。

## 自动验证与全面生产判断

三部候选均为 `AUTOMATED_QA_PASSED`。检查包括 source rehash、v20 technical-ready、
显式 composition、835/836/1681 排除、每 event 一个 scene SE、voice 保留、零黑场、
原生尺寸/帧率、精确帧/样本栅格、单次 AAC、SRT 回读及人审状态为 false。
首/中/尾共 36 张字幕布局帧已生成供快速抽查。

代码回归在设置耐久 D: 资源根后为 314/314 tests passed；`compileall`、全部 Frida JS
`node --check`、198 个 JSON parse 和 `git diff --check` 均通过。

当前判断：**同一 SP Story、单全画面线性 composition、v20 technical-ready、voice/SE
证据完整的事件已经具备批量生产条件**。仍不应把这个结论自动外推到全部 926 event：
多层 composite、loop、gameplay/result、material 和音频证据未闭合项需要各自合同。
若项目所有者确认这三部完整章节均正常，下一轮即可扩大所有满足同一合同的剧情 family，
并将低置信度/不同 composition class 单独留在失败关闭队列，而不是逐 event 手工制作。

## 当前人工审查点

每个 family 目录内需要完整播放：

```text
video/<family>_full_no_bgm_zh_review_v1.mp4
```

并参考：

```text
review/HUMAN_PLAYBACK_REVIEW.md
review/layout_frames/*.png
```

请重点确认自然场景顺序/边界、voice/SE、是否意外出现 BGM、中文字幕语义与时间、
音画同步、尾帧保持以及是否混入老虎机效果。收到项目所有者反馈前，不把候选提升为
`HUMAN_PLAYBACK_APPROVED` 或继续下一生产批次。
