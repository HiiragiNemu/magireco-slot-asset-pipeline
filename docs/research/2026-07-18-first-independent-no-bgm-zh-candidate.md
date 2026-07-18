# 2026-07-18 首个独立 `no_bgm_zh` 长片候选

## 项目所有者发布优先级覆盖

项目所有者已把首个可人工观看的 Bilibili 中文剧情长片置于最高优先级。旧的
`with_bgm` / `no_bgm` 两条音频母版乘无字幕/日文/中文三种字幕的六版合同仍是
`archive_complete` / `six_edition_complete` 的最终归档目标，但不再原子阻塞证据完整的
单一 edition。

本轮新增的最小正式构建单位只有一个命名合同：

```text
release_profile = bilibili_no_bgm_zh_v1
audio_profile = no_bgm
subtitle_profile = zh_dialogue_only
release_scope = independent_edition
bgm_policy = intentionally_excluded
voice_se_policy = preserve_verified_original
archive_complete = false
six_edition_complete = false
```

它的公开规格名称是“无 BGM 中文字幕版（保留原始对白与音效）”。它不声明游戏原本
没有 BGM，也不声明已完成原游戏完整音轨或六版归档。旧六版事务工具未被降级；新合同
只为该独立 R1 产品建立自己的 fail-closed 构建、QA 和 READY 边界。

## P1 runtime-event 重复项已关闭

此前 `load_runtime_event_manifests()` 对多个 root 中的同名 event 静默
`last-wins`。本轮规则改为：

- 去除 loader 自己写入的 provenance 字段后，内容冲突的重复项立即 fail closed；
- 内容完全等价的重复项允许继续，但保留每一份来源的绝对路径和文件 SHA-256；
- production manifest 写入完整的 `runtime_event_manifest_sources`，不再静默覆盖。

相关正向/负向测试覆盖等价重复与声音内容冲突。

## 首个候选的组成

事件顺序由现有 composition/runtime 证据固定为：

```text
ac7114_001 -> ac7115_001 -> ac7116_001
```

三段连续拼接，插入黑场帧为 0：

| event | frame 区间 | presentation sample 区间 |
|---|---:|---:|
| `ac7114_001` | 0--288（289 帧） | 0--462399（462400） |
| `ac7115_001` | 289--954（666 帧） | 462400--1527999（1065600） |
| `ac7116_001` | 955--1345（391 帧） | 1528000--2153599（625600） |

总计 1346 帧、2,153,600 个 48 kHz presentation samples，即 44.8667 秒。画面保持
原始 512x288、30/1 fps，不 upscale；最终视频为 H.264 1,053,224 bit/s，音频为 AAC
193,249 bit/s、48 kHz stereo。

音频由 15 个 hash-bound OGG 层组成：12 个 voice 与 3 个 `scene_se`。`bgm_layers=[]`，
即没有 BGM 层；金带/老虎机前景音 request 1681 也显式排除。每个事件按精确样本数
trim/pad，连续 PCM 混合后只编码一次 AAC；最终文件与音频母版的 packet 和 decoded PCM
hash 均相同。

用户先前已确认 v19 三段的语音/字幕关系正确。新构建对同一已确认声音 oracle 做双声道
APSNR 回归，门限为 80 dB，结果全部通过：

| event | 左声道 APSNR | 右声道 APSNR |
|---|---:|---:|
| `ac7114_001` | 166.504 dB | 166.523 dB |
| `ac7115_001` | 167.862 dB | 167.903 dB |
| `ac7116_001` | 167.019 dB | 167.215 dB |

## 中文字幕范围

SRT 只有 9 条与可靠语音绑定的剧情对白。`ac7115_001` 的图形文字
`ごめんね…` 已按 `graphical-only` 排除；UI、标题、名牌、装饰/背景文字也不进入本版。
字体使用固定 hash 的 Noto Sans SC 审计 fallback；它不是游戏原生字形。布局 profile
为 `project_approved_zh_video_subtitle_layout_v1`，但其
`approval_status=pending_owner_review`。当前翻译状态同样是
`machine_draft_pending_owner`，不得把 profile 名称误读为已经获得项目所有者批准。

## 自动 QA 与耐久输出

输出根：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\bilibili_candidates_v21_no_bgm_zh_20260718\ac7114_16_sp_story_no_bgm_zh_v1
```

自动 QA 的 21 项合同检查全部为 `true`，包括来源构建前后 rehash、顺序、零黑场、原生
尺寸/帧率、精确帧与样本数、单次 AAC、oracle 回归、空 BGM、1681 排除、图形字幕排除、
SRT 回读、9 cue 和 no-upscale。

设置 `MAGIRECO_SLOT_ASSET_ROOT` 为耐久 D: 资源根后的最终全仓回归为 307/307 tests
passed，0 skipped/failed/error。

当前 D: 成品 hash：

| artifact | SHA-256 |
|---|---|
| `video/ac7114_16_sp_story_no_bgm_zh_v1__no_bgm_zh.mp4` | `E4A5F8D8B4621FCD256B1E4471F4E2EA6116C1BC382A21D8F07B8DEFB7719D3B` |
| `subtitles/ac7114_16_sp_story_no_bgm_zh_v1__zh_dialogue.srt` | `5FA6851A4F12DAB38FF4145B0AFE319169EC713D807B801FBA373F898277E9C9` |
| `manifests/scene_release_manifest.json` | `06AF2D23DCAB258536422ABDC82373117B8649B9E15F0A6ACC88F85A06135BCB` |
| `qa/automated_qa.json` | `05B2F39B02459B50353C1D25768AF2DFE2BEA1E9B4CC279AC38C93C0BD4E249C` |
| `EDITION_BUILD_READY.json` | `DEF8ADEA197BA49FE5CCB0A1F2D470D661767ECD68B237C44011A0B93AEDE0EC` |

`EDITION_BUILD_READY.json` 当前只证明：

```text
BUILD_READY = true
AUTOMATED_QA_PASSED = true
HUMAN_PLAYBACK_APPROVED = false
BILIBILI_RELEASE_READY = false
publishable = false
```

## 当前停止边界

项目所有者需要完整播放 MP4，并在 `review/HUMAN_PLAYBACK_REVIEW.md` 中审查画面、边界、
语音、SE、是否意外出现 BGM、9 条翻译/排版、音画同步和首尾。只有项目所有者可以把
人工状态改为 true。

候选和自动 QA 完成后立即停止：未开始第二部长片、全库批量、素材分类、BGM 捕获、
CDN/addon 研究或进一步发布架构重构。下一步等待项目所有者播放反馈。
