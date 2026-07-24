# 2026-07-25 Codex 项目接手核心说明

本文件是上下文迁移用的最新入口。接手者还应阅读：

- `docs/HANDOFF_NEXT_AI_MAGIRECO.md`
- `docs/PROJECT_STATUS.md`
- `docs/research/2026-07-24-mass-no-bgm-production-and-environment-recovery.md`

如旧文档与本文件、项目所有者在 2026-07-25 的播放审查结论冲突，以最新播放审查
结论为准。

## 1. 长期目标

基于游戏运行时和可验证静态证据，在外部复刻《魔法纪录 Slot》的媒体调度，保存
原始单事件，同时生产适合 Bilibili 连续观看的自然场景／章节长片：

- 保持源画面分辨率、30 fps、合理原生码率等级，不 upscale；
- 正确恢复画面层、循环、尾帧行为、角色语音、SE、事件边界和累计时间轴；
- 剧情与老虎机 sparkle/logo/粒子/玩法效果分离；允许另做“有特效版”和效果合集；
- 先全面生产 `no_bgm` 的无字幕、日文字幕、中文字幕版本；
- 中文完成后再扩展中日对照版；
- BGM 身份、入口 phase、fade/duck/stop 闭合后，再补完整 BGM 版本；
- 纯素材、带 SE 素材、玩法、结果画面和效果层分别建立可审计合集；
- 每个产品保留 manifest、source SHA-256、event index、累计时间轴、QA 和人工审查状态。

项目所有者自己上传 Bilibili。Codex 只负责本地生产、审计、人工验收包和 GitHub
文本／工具更新。

## 2. 当前发布策略

`no_bgm` 的准确含义是“有意排除 BGM，保留已验证的原始对白与 SE”，不得宣称
“游戏原本没有 BGM”或“完整原游戏音轨”。

首批工作流已经多轮人工播放通过，可扩大生产；但遇到证据歧义、音画同步疑点、
自然场景顺序疑点或角色身份疑点时，应生成数量有限、差异明确的候选并停止，请
项目所有者人工观看。不要靠 Codex 反复肉眼自判。

## 3. 仓库和耐久路径

唯一工作分支：

```text
codex/corrected-runtime-pipeline
```

2026-07-25 本轮开始时的基线：

```text
c0a87cbf5ea763c9c2915f28d2968384609d402e
Scale evidence-bound no-BGM production
```

当前 Codex worktree：

```text
C:\Users\proje\.codex\worktrees\7454\
  com.universal777.magireco-Ga9DaxEd9F9Lqn9OVKVSfw==
```

主要耐久研究根：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612
```

游戏导出／分析根：

```text
D:\magia\MyProducts\casino\
  com.universal777.magireco-Ga9DaxEd9F9Lqn9OVKVSfw==
```

最新生产：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  no_bgm_editions_v24_mass_20260724

D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  no_bgm_editions_v25_next_story_20260724

D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  bilibili_upload_ready_v25_no_bgm_20260724_16families
```

投稿包根目录的 `zh` 只有 P11–P25。修正版 P10 在：

```text
bilibili_upload_ready_v25_no_bgm_20260724_16families\
  replace_old_p10_ac5203\zh
```

P1–P9 分散在较早的 v21/v22 耐久审查根；不要声称所有成品都位于 v25 `zh`。

## 4. 最新人工审查纠错

### 4.1 黑羽、黑、黑江是三个不同身份

游戏声源标签中的原始 `speaker_code=kuro` 有上下文歧义，不得做全局人物映射：

```text
黑羽 / 黒羽 -> canonical speaker: kuro_black_feather
黑   / 黒   -> canonical speaker: kuro_character
黑江 / 黒江 -> canonical speaker: kuroe
```

项目所有者明确确认：

- P12 `ac4902` 两次“くそっ！／可恶！”是黑羽；
- P23 `ac7117` 白衣奔跑、喘息角色是黑，不是黑羽，也不是黑江；
- 原始 `kuroe` 始终与上述歧义 `kuro` 分离。

本轮已把规则改为 event + request + code name + audio SHA-256 的精确绑定。关键
文件：

```text
tools/frida_runtime_probe/speaker_display_registry_v1.json
tools/frida_runtime_probe/speaker_identity_overrides_v1.json
tools/frida_runtime_probe/owner_attestations/
  kuro_black_feather_kuro_kuroe_correction_20260725.json
```

已授权的精确映射：

```text
ac4902_003 req8340 -> 黑羽
ac4902_059 req8340 -> 黑羽

ac7117_001 req9634 -> 黑
ac7117_001 req9635 -> 黑
ac7117_006 req9638 -> 黑
ac7117_013 req9663 -> 黑
```

其他尚未获得身份验证的原始 `kuro` 不加人物名前缀，不得类推。

P23 标题也不应继续写“黑江与陌生魔法少女的相遇”；可在重建候选中使用
“黑江与黑的相遇 ac7117”，最终仍由项目所有者确认。

### 4.2 P16 `ac6003`

旧标题“彩羽等人与 Magius 的冲突”错误，画面主体是八千代与美冬／Magius。
建议候选标题：

```text
八千代与美冬的冲突 ac6003
```

项目所有者在约 47 秒开始明确观察到语音早于张嘴。该位置正好进入
`ac6003_009`：该事件占全片 45.667–52.467 秒。当前 manifest 把画面排为：

```text
c01_MR:     0–467 ms
c02_MR:   467–5833 ms
c02_MR_LP: 5833–6800 ms
```

request 2143 的事件 SE、request 5843 的美冬对白和字幕都被放到事件 0 ms。
`z2d_audio_timeline_v2` 中的 `absolute_start_frame=0` 只证明子 Z2D
`cap6003_mb_mif_007` 自身的 callback frame，没有证明该子 Z2D 相对父 DGM 的
实例化偏移。当前管线把 child-local 0 直接晋升成 event-global 0，属于证据越级。
request 5843 的对白身份正确，未知的是时点。

因此不要根据 467 ms lead-in 目测猜偏移。先隔离 P16；从官方同 run 捕获或父
DGM→子 Z2D 实例化记录取得精确父偏移，再用 hash-bound per-event override
同时平移 request 5843 与对应字幕。人工修复验收只需重点观看 45.667–52.467 秒
及进入 `ac6003_010` 的边界。

另外，DirInfo 已表明 `_009/_010/_014/_015` 含分支关系；旧长片是分支汇编，
不是已证明的单一路线。

P16 当前 production event manifest：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  production_manifests_v24_timing_and_reviewed_subtitles_20260724\
  events\ac6003_009.json
SHA-256:
9F90BFE29DF505E980897421ABB430650E1C49F236466B17680B98243F196E46
```

### 4.3 P18 `ac6005`

旧 P18 缺少彩羽扑向灯花、音梦的后半段。静态证据定位到：

```text
ac6005_014:
  req2793 灯花ちゃん！ ねむちゃん！
  req2794 もうお姉ちゃんを置いていかないでよ！
  req2795 后续对白

ac6005_015:
  req6639 お願いお姉ちゃん ふたりを助けてあげて

ac6005_016:
  ac6005_014 的另一 timing/route 版本
```

`_014/_015/_016` 都混合 512x416 剧情片段与 320x256 `ac8040_shouri_EF_*`
胜利／玩法效果。剧情候选只组合 512x416 故事层；`ac8040` 效果另入玩法／效果
合集。不要把两种画布强行合成一个剧情长片。

DirInfo v3 kind 173 已明确证明这些互斥路线：

```text
row 7:  010 → 011 → 012  普通失败
row 8:  010 → 013 → 012  CU 失败
row 9:  010 → 011 → 014  普通成功
row 10: 010 → 013 → 014  CU 成功
row 11: 015 → 016        复活分支
```

现片把互斥的 `_011/_012/_013` 机械串联。项目所有者描述的“彩羽扑倒灯花和
音梦”属于 CU 成功路线，下一步应优先、且只先制作：

```text
ac6005_010 → ac6005_013 → ac6005_014
```

`ac6005_014` 已由 event_info、DirInfo selector、`event_timeline_events.csv`
中的 `WIN` 和音频父请求 2190 证明存在；它是 component-only，多画布／多层，
因此被旧 `native_full_frame_only` 筛选错误漏掉。必须为 `_014` 建立正式
component composition plan，不能把 component clips 线性 concat。先完整人工
验收 CU 成功线，再决定是否生产其他四条明确命名的分支。

主要路由证据：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\
  dirinfo_event_table_decode_v3_20260703\dirinfo_event_routes.csv
SHA-256:
44202FCB8186D9577C33A4A20C492CFC84BFDD94DEC4EE76EB22DF8F4444DC01
```

### 4.4 重复内容

25 部现有长片共 267 个事件单元、约 47:52.932。精确 AV+字幕签名发现 26 个
重复 occurrence；面向观众的长片去重后是 241 单元、约 41:23.432，可减少
389.500 秒。重复集中在：

```text
ac0915: 3
ac4902: 21
ac5203: 1
ac5301: 1
```

本轮已增加 fail-closed 精确重复门禁。单事件档案不删除，只从面向观众的路线
proposal 去掉重复 occurrence。

`ac1102/ac1103/ac1104` 没有完整 AV+字幕精确重复；其相似内容多为 title color、
S/L、Kuroe add、CU、win/revival/CLEAR 等真实路线变体。不要自动删除，但应该
在 Bilibili 产品中明确标成支线／替代版本，避免伪装成自然线性剧情。

`ac5203` 除完全重复的 `_005/_017` 外，还有 S/M/L、CU 和独立对白等真实分支。
正确产品应标为分支／攻击展示，不能按文件后缀猜“官方自然顺序”。

## 5. 当前规模与剩余估计

截至人工反馈前：

- 25 个无 BGM 面向观众的长产品；
- 75 个 none/JA/ZH MP4；
- 267 个已纳入事件单元；
- 技术 READY 基线 521 event；
- 304 event 有旧逐事件 QA；
- 约 217 event 仍缺现代单事件渲染／QA。

面向观众的剧情／动画长产品预计最终约 38–45 部，即还约 13–20 部，但另外
225 个事件单元仍需剧情、分支、玩法和素材语义分类。单事件三版的理论上限为
1,563 MP4。现代素材／玩法／效果合集预计最终约 40–55 组，目前只约 6 个旧逻辑
合集，仍有约 34–49 组需要现代化生产。

下一批证据较成熟的是 `ac7101–ac7107`、`ac0908`、`ac6002`，约 9 个产品。
`ac7101–7107` 的 `_001→_002` 是干净故事，`_003` 是 1 秒控制／停止事件，应
排除；共约 19:50。先完成当前 P12/P16/P18/P23 纠错验收，再批量进入该组。

## 6. 当前代码状态

本轮工作树包含三组尚待统一提交的改动：

1. aggregate auditor：验证 source snapshot 覆盖所有 ordered manifests、clips、
   upstream audio，并重新哈希；
2. audience exact-duplicate gate：按 clean visual、音频、时间、字幕和说话人
   组成精确内容签名，重复即 fail closed；
3. 三身份 speaker 修复：原始 `kuro` 不再全局映射，改用精确哈希绑定的 contextual
   identity override；`kuroe` alias 保持独立。

已完成的聚焦测试：

```text
python -m unittest test_audit_no_bgm_mass_production_v24.py
18/18 passed

python -m unittest \
  test_build_no_bgm_story_family_editions.py \
  test_runtime_pipeline.py
50 passed, 1 skipped

PATH 加入现有 Node.js 与 WinGet FFmpeg links 后：

python -m unittest
365 passed, 5 skipped
```

交接前或下一任务开始时还应：

- 检查完整 diff；
- 跑一次全仓回归、compileall、JSON parse、diff check；
- 更新本文件和 `PROJECT_STATUS.md` 的最终提交 SHA；
- 只提交到 `codex/corrected-runtime-pipeline` 并 push；
- 大型媒体不上传 GitHub。

## 7. 环境

当前已确认：

```text
Python 3.14.6
Git 2.55.0.windows.3
GitHub CLI 2.96.0
FFmpeg/ffprobe 8.1.2 full
Node.js 24.18.0 LTS
Frida 17.16.4
frida-tools 14.10.4
```

FFmpeg 的耐用显式路径：

```text
C:\Users\proje\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe
C:\Users\proje\AppData\Local\Microsoft\WinGet\Links\ffprobe.exe
```

旧终端 PATH 找不到 FFmpeg 时直接使用该路径，不要重复下载安装。

MuMu 和 Slot 游戏已在主界面，可用于必要的最小运行时验证；当前优先级仍是修正
已报告产品并交付人工审查，不应先扩展新的宽泛动态 hunt。

## 8. 接手后的立即执行顺序

1. 复核并提交本轮 aggregate、duplicate、三身份 speaker 改动。
2. 用 contextual identity 规则重建 P12/P23 的 JA/ZH 候选；P12 同时使用去重、
   route-aware proposal。
3. 隔离 P16，取得 `ac6003_009` 父 DGM→子 Z2D 的精确实例化偏移后重建，并
   改标题；不要靠 467 ms lead-in 猜值。
4. 先建立 P18 的 `010→013→014` CU 成功路线；为 `_014` 做多层 component
   composition plan，排除另属玩法展示的 `ac8040` 效果层。
5. 把候选放入一个新的 D: 人工审查根，给出只需观看的明确 MP4 清单并停止。
6. 只有项目所有者回报通过后，才继续 `ac7101–7107/ac0908/ac6002` 和更大批量。
7. 每批同步 GitHub 文档、manifest/hash 摘要和自动 QA；上传 Bilibili 仍由所有者
   自己完成。

## 9. 永久禁止的旧做法

- 不生成旧 124 GB 1080p 输出；
- 不 upscale；
- 不删除原始单事件；
- 不使用旧 motion/static 二分法决定剧情／素材；
- 不按 `ac` 后缀数字直接寻找 CRI index 或猜播放顺序；
- 不混淆字幕版与无字幕版；
- 不把五段 DGM 或所有分支机械 concat 成“自然故事”；
- 不把老虎机金框、sparkle、logo、粒子默认叠进干净剧情版；
- 不把未知声音猜成 SE，不把当前无 BGM 解释成原游戏没有 BGM；
- 不根据视觉相似度猜角色语音／字幕；身份、声音和调度必须绑定逻辑证据；
- 不在遇到音画疑点时无限自行重试；制作有限候选后转人工播放审查。
