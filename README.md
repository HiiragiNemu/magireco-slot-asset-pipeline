# Magireco Slot Asset Pipeline

这是一个本地资产审计与整理工具仓库，用于继续处理当前解包工程中的视频、图像、音频清单、命名、分类和候选拼合分析。

可复现输入布局、已验证版本指纹、外部工具锁定和派生证据 Release
打包流程见 [reproducibility/README.md](reproducibility/README.md)。

仓库只保存脚本和轻量文档，不保存 APK、解包素材、JADX 反编译源码、native 库、视频、图像或音频文件。原始游戏数据需要放在本地工作目录中，由 `.gitignore` 排除。

## 当前状态

> **2026-07-18 非线性／多层扩产检查点：** 项目所有者已确认 Story 3/4/5 三部完整
> 章节全部通过并授权全面生产；原话和三部 artifact hash 已写入 owner attestation。
> 随后构建器已越过“单全画面线性 SP Story”：首批 `ac1102/ac1103/ac1104/ac5208`
> 覆盖 40 event、99 条 voice-bound 中文字幕、175 个声音层、21 个 linear event 与
> 19 个 `timed_full_frame_layers`，包括多片段、loop background、screen overlay、
> loop overlay、416x232 与 512x288，总时长 315.067 秒。四部长片均通过精确帧／样本
> 自动 QA，保持原生尺寸、30 fps、H.264、AAC 48 kHz stereo，明确排除 BGM；当前仍为
> `HUMAN_PLAYBACK_APPROVED=false`、`BILIBILI_RELEASE_READY=false`，已停止等待项目
> 所有者播放，尤其检查运行时 sparkle/logo 是否应留在 clean-story、并发对白字幕和
> 416x232 布局。详见
> [非线性／多层剧情首轮扩产审查批次](docs/research/2026-07-18-mixed-composition-expansion-review-batch.md)。
> 已通过的前三部完整章节及其旧检查点见
> [SP Story 完整章节首轮扩产审查批次](docs/research/2026-07-18-sp-story-chapter-expansion-review-batch.md)。
> 本轮全仓回归为 319 tests passed、4 skipped、0 failed/error。

> 2026-07-16 存储约束：A: RAMDISK 已关闭，不再作为输入、scratch 或输出路径。
> 耐久研究/媒体一律写入 `D:\magia\MyProducts\casino`，仓库和小型临时处理使用 C:
> SSD。任何旧 A: 路径只可作为历史 provenance，必须通过显式、可哈希验证的 D: 路径
> 映射读取，禁止重新依赖 A:。

> 2026-07-15：权威开发分支是 `codex/corrected-runtime-pipeline`。当前已由
> `libGameProc.so` 的 `C_ObjNml::fnSndRequest_BGM_DIR` 静态闭环证明业务声音代码
> 835/836 都是 BGM 请求，并完成从 `SoundMng` 到跨线程 `CSLMng::PlayStart` 的
> 精确播放身份连接；用户也确认对应自然运行批次中确实听到了 BGM。听检时间尚未与
> 835 或 836 中的单一首曲目唯一绑定，因此目标场景仍须保存同一次运行的曲目、循环
> 相位、音量和切换证据，不能靠听感或时间邻近猜测。详见
> [BGM_DIR 与 CSL 跨线程身份链](docs/research/2026-07-15-bgm-dir-and-csl-cross-thread-identity.md)。
> 目标 SP Story 的上游静态链进一步证明：ac7114/15/16 自身不请求 BGM，而是继承
> 全局 Direction `kind/no`；DirInfo 190/191/192 绝不是 BGM 的 `no`。详见
> [目标 SP Story BGM 状态上游](docs/research/2026-07-15-target-sp-story-bgm-state-upstream.md)。
> 2026-07-16 已把该上游链实现成 fail-closed observer，并在 PID3188 完成 8 秒零输入
> 预检：已安装 split APK 与其中 STORED GameProc ELF 双重完整哈希匹配，13/13 hooks
> 安装、0 unavailable/error、973 条 sound metadata 零丢失、未发送输入。该检查只证明
> 捕获器已就绪；自然目标同 run 仍是最终 BGM 门禁。
> 随后真实单回合暴露的高频 signature 溢出已失败关闭并修复；第二个 bounded
> non-target 回合以 40/1024 条上游记录、0 drop/error 完成，证明 observer 已通过
> 实际负载，但该回合没有目标 SP Story 或 835/836。
>
> 完整归档规格仍为两条经证据约束的音频母版（`with_bgm` / `no_bgm`）乘三种字幕
> （无字幕 / 日文 / 中文），共六版。项目所有者 2026-07-18 的覆盖允许满足自身证据
> 合同的 `no_bgm_zh` R1 独立获得 BUILD_READY；人工播放批准仍是 Bilibili 投稿硬门禁。
> clean visual、双音频母版、字幕六路以及 scene 长片均采用失败关闭的
> manifest/hash/逐帧逐样本 QA。完整归档合同与实现状态见
> [双音频母版与六版合同](docs/research/2026-07-14-two-audio-master-six-edition-contract.md)。
> event/scene/series/material 的 AAC 样本边界、SRT 回读、source rehash、staging/READY、
> 并发 no-replace 与失败回滚加固见
> [六版发布流水线加固](docs/research/2026-07-16-release-pipeline-hardening.md)。
>
> 真实 v20 manifest 已在 D: 重建：926 个事件中 521 READY、405 fail-closed；
> ac7114/15/16 的 512x288、30 fps、H.264 clean visual 已分别通过 289/666/391
> 精确帧 QA。双母版和 scene 六版引擎已经实现；完整六版归档仍阻塞于自然目标同 run
> 的 BGM ID/phase/volume/transitions。独立 R1 已不再等待该 BGM 门禁，目前只等待项目
> 所有者对首个中文候选的翻译、布局和完整播放确认。设置 D: 真实资源根后，前一检查点
> 自动测试为 289/289 passed、
> 0 skipped/failed/error。
> 2026-07-18 的同步边界、已修复发布缺陷以及已经关闭的重复 runtime-event
> `last-wins` P1 见
> [上传前状态与已知问题](docs/research/2026-07-18-prepush-status-and-known-issues.md)。

面向项目所有者和外部读者的最新中文进度、静态/动态机制边界、三版本字幕规格、
CDN 高分辨率备选路线和量化剩余工作见
[docs/HUMAN_PROGRESS_REPORT_2026-07-13.md](docs/HUMAN_PROGRESS_REPORT_2026-07-13.md)。
三项只读审计的完整证据边界见
[docs/research/2026-07-13-static-generality-font-and-cdn.md](docs/research/2026-07-13-static-generality-font-and-cdn.md)：
它明确区分 Slot 与 Exedra 下载机制，并记录静态通用性和游戏字体门禁。
当前 Sound Pack entitlement、222 项原生静音表和 BGM 结论边界见
[docs/research/2026-07-14-sound-pack-entitlement-gate.md](docs/research/2026-07-14-sound-pack-entitlement-gate.md)；
全部 7 个付费 SKU、native 字段/xref、角色/设定/强制役影响、当前 PID3188 只读快照
和 CDN 高清结论见
[docs/research/2026-07-16-paid-addon-gates-and-archive-impact.md](docs/research/2026-07-16-paid-addon-gates-and-archive-impact.md)；
设定 0..5/随机、五角色 profile、强制役 0..19 与 SP Story 独立路由的完整静态枚举见
[docs/research/2026-07-16-setting-character-force-variant-space.md](docs/research/2026-07-16-setting-character-force-variant-space.md)；
JM 位图字形的可复现导出/缺字门禁见
[docs/research/2026-07-14-jm-dgi-glyph-catalog.md](docs/research/2026-07-14-jm-dgi-glyph-catalog.md)。
中文字幕使用的独立可审计字体依赖、固定上游 commit、字体/许可证 SHA-256、离线缓存
校验及 ac7114/15/16 候选字符 34/34 覆盖见
[reproducibility/fonts/README.md](reproducibility/fonts/README.md)。该字体明确标为
`audited_chinese_fallback`，不是游戏原生字体；翻译与布局未人工批准前仍失败关闭。
ac7114/15/16 的中文字幕原始审阅表与 JM 缺字实测见
[docs/review/2026-07-15-ac7114-16-chinese-subtitle-review.md](docs/review/2026-07-15-ac7114-16-chinese-subtitle-review.md)；
R1 已从中排除 `graphical-only` 的 `ごめんね…`，只渲染 9 条对白；翻译和布局仍是
等待项目所有者播放批准的草案。

接手或恢复工作时先读
[docs/HANDOFF_NEXT_AI_MAGIRECO.md](docs/HANDOFF_NEXT_AI_MAGIRECO.md)；它是唯一
核心入口。最新自然 SP Story hunter、停轮权威门禁、静态抽奖表和量化剩余工作见
[docs/research/2026-07-13-natural-sp-story-hunter-and-lottery.md](docs/research/2026-07-13-natural-sp-story-hunter-and-lottery.md)。
前一轮 MuMu 重连与声音链基线见
[docs/research/2026-07-12-runtime-reconnect-and-completion-gap.md](docs/research/2026-07-12-runtime-reconnect-and-completion-gap.md)。
滚动审计结论见 [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md)。

下方历史统计用于资产盘点，不等于已经通过语音、字幕、BGM 和场景语义门禁
的可投稿成片数量；发生冲突时以核心 handoff 和最新 dated delta 为准。

当前执行顺序以
[核心交接](docs/HANDOFF_NEXT_AI_MAGIRECO.md)、
[首个独立 no_bgm_zh 候选](docs/research/2026-07-18-first-independent-no-bgm-zh-candidate.md)、
[人类可读报告](docs/HUMAN_PROGRESS_REPORT_2026-07-13.md) 和
[双音频母版 × 三字幕合同](docs/research/2026-07-14-two-audio-master-six-edition-contract.md)
为准。

[旧 NEXT_STEPS](docs/NEXT_STEPS.md)、
[旧官方事件流程](docs/OFFICIAL_EVENT_PIPELINE.md) 和
[旧 B站分P流程](docs/BILIBILI_PRODUCTION_WORKFLOW.md) 仅保留为历史审计材料；其中的
视觉候选、两版、1920×1080 upscale、全局 limiter/loudness 和 `--edition both`
命令均禁止用于当前生产。

本阶段研究记录见
[docs/RESEARCH_LOG_2026-06-05.md](docs/RESEARCH_LOG_2026-06-05.md)。

当前最终生产不再使用 `main_video_NNNN_candidatesX` 数字候选关系，也不使用
`low_motion` / `short_static` / `static_like` 目录做判断。权威链路为
`GDB event -> Z2D -> DGM -> native CRI -> MP4`。

主要结果：

- 精确官方事件：7753
- 精确事件/画布输出：8482
- 有声无字幕输出：5201
- 有声有字幕输出：284
- 静音视觉输出：2997
- 已全量验证有声事件/画布：5485
- 有声B站分P计划：294
- 视频 CRID chunk：7801
- 可唯一命名视频 chunk：483
- 多候选共享视频 chunk：607
- 直接无 GDB 候选视频 chunk：6711
- z2d 图像 chunk：12083
- z2d 名称引用：11733
- OGG chunk：9952
- `sound_id.dat` 音频映射记录：9951
- 含内嵌 `@SFA` 音频的视频 slice：456
- PCM chunk：21
- 视频连续序列候选：263，其中 175 组为旧候选分析结果，不用于最终官方事件合并

## 不上传的数据

公开仓库不包含：

- `*.apk`, `*.obb`, `*.bin`, `*.dat`, `*.mp4`, `*.ogg`, `*.z2d`
- `downloaded_assets/`
- `unpacked_assets/`
- `unpacked_base/`
- `unpacked_lib/`
- `jadx_audit/`
- `asset_manifests/`
- 临时导出、最终视频、JADX GUI 工具包

这些内容体积很大，并且可能包含专有游戏数据。需要时在本地重新生成。

## 常用命令

生成基础资产清单：

```powershell
python magireco_asset_pipeline.py manifest
```

生成 Java/smali/native/GDB/m_info/sound_id 交叉审计报告：

```powershell
python magireco_internal_audit.py
```

音频导出 dry-run，按 `sound_id.dat` 给 OGG 命名：

```powershell
python magireco_asset_pipeline.py export-audio --sound-id-names --limit 5
```

实际导出音频：

```powershell
python magireco_asset_pipeline.py export-audio --sound-id-names --execute
```

视频整理 dry-run：

```powershell
python magireco_asset_pipeline.py organize-videos
```

对已导出的 MP4 生成序列复核报告，不合并视频：

```powershell
python magireco_asset_pipeline.py video-review --video-dir D:\MagiaRe_RAMDISK_Backup_20260603_032042\magireco_final_mp4_videos --write-concat-plans
```

解析 `zg_snd_request_tbl.bin`，生成声音请求 ID、描述标签、候选 `.smz/.pcm` 媒体名与 `sound_id.dat` 的关联审计：

```powershell
python magireco_asset_pipeline.py sound-request-audit
```

按 native `RequestCtrl::loadRequestTbl()` 的结构解析 `zg_snd_request_tbl.bin`，生成精确的 code -> request id -> ReqData/SMZ 审计：

```powershell
python magireco_asset_pipeline.py sound-request-struct-audit
```

审计声音请求表中的 `.smz/.pcm` 媒体名、`zg_snd_hashreq_tbl.bin` 哈希请求表，以及可选的安装态 `smz.bin/smz_add.bin`：

```powershell
python magireco_asset_pipeline.py sound-media-audit --smz-bin D:\magia\MyProducts\casino\magireco_installed_pull_20260603\data_user_0\files\assetpacks\OnDemandPack01\31\31\assets\smz.bin --smz-add D:\magia\MyProducts\casino\magireco_installed_pull_20260603\data_user_0\files\assetpacks\OnDemandPack01\31\31\assets\smz_add.bin
```

当前版本还会读取 `libGameProc.so` 中 `loadFileSmz` / `loadFilePcm` 的 relocated name table，生成官方媒体名到安装态 chunk 的对应表：

```text
asset_manifests/smz_name_chunk_map.csv
asset_manifests/pcm_name_table.csv
asset_manifests/smz_request_missing_from_installed_pack.csv
```

注意：`zg_snd_hashreq_tbl.bin` 的 request id 是记录序号，第三个 `u32` 是 sample/play length 字段，不是 request id。

从已有 native 字符串清单中提取声音请求、SMZ 表和 `EVT_ac` 事件标签证据：

```powershell
python magireco_asset_pipeline.py native-sound-video-audit
```

扫描已导出的 MP4，收集纯音频、无视频流、全黑或近黑画面复核候选：

```powershell
python magireco_asset_pipeline.py review-special-videos --video-dir D:\magia\MyProducts\casino\magireco_bili_fulltest_20260603\videos --out-dir D:\magia\MyProducts\casino\magireco_bili_fulltest_20260603\review_special
```

对已导出的 MP4 做水平翻转校正，输出到新的目录，不覆盖源目录：

```powershell
python magireco_asset_pipeline.py hflip-videos --input-dir D:\magia\MyProducts\casino\magireco_bili_fulltest_20260603\videos --out-dir D:\magia\MyProducts\casino\magireco_bili_fulltest_20260603\videos_hflip --execute --encoder h264_nvenc --workers 2
python magireco_asset_pipeline.py hflip-videos --input-dir D:\magia\MyProducts\casino\magireco_bili_fulltest_20260603\videos --out-dir D:\magia\MyProducts\casino\magireco_bili_fulltest_20260603\videos_hflip --execute --encoder libx264 --workers 4
```

对方向正确的视频树重新做复核，并用 `volumedetect` 区分可听音轨和静音音轨：

```powershell
python magireco_asset_pipeline.py review-special-videos --video-dir D:\magia\MyProducts\casino\magireco_bili_fulltest_20260603\videos_hflip --out-dir D:\magia\MyProducts\casino\magireco_bili_fulltest_20260603\review_special_hflip_audible --audio-volume --workers 4
```

将导出的 `.pcmraw` 封装为 foobar2000 可播放的 WAV：

```powershell
python magireco_asset_pipeline.py convert-pcm-wav --input-dir D:\magia\MyProducts\casino\magireco_bili_fulltest_20260603\audio_assets\audio\pcm_raw --out-dir D:\magia\MyProducts\casino\magireco_bili_fulltest_20260603\audio_assets\audio\pcm_wav_48k_stereo --execute --overwrite --audio-volume --workers 4
```

按 `MultiCandidate_Slices` 中连续的 `main_video_NNNN_candidatesX` 切片做候选数合并测试：

```powershell
python magireco_asset_pipeline.py merge-candidate-runs --video-dir D:\magia\MyProducts\casino\magireco_bili_fulltest_20260603\videos --out-dir D:\magia\MyProducts\casino\magireco_bili_fulltest_20260603\merge_tests\candidate_runs_command_execute_hflip_video_only --execute --hflip --drop-audio --probe
```

生成面向 B 站整理的标题、标签和说明候选报告：

```powershell
python magireco_asset_pipeline.py bili-metadata-audit
```

官方 GDB -> Z2D -> DGM -> CRI 事件重建、音频、字幕和分 P 工作流见：

```text
docs/OFFICIAL_EVENT_PIPELINE.md
docs/BILIBILI_PRODUCTION_WORKFLOW.md
```

对已生成的 B 站分 P 做独立的流、音量、时长和硬链接审计：

```powershell
python magireco_asset_pipeline.py bilibili-part-output-audit --help
```

在实际 SRT 字幕时间点比较无字幕与烧录字幕画面：

```powershell
python magireco_asset_pipeline.py subtitle-burn-audit --help
```

当模拟器已运行并且 Android 侧有匹配版本的 `frida-server` 时，可以探测 native WAV 转换入口。无 `--code` 参数时只做状态检查：

```powershell
python tools\frida_smz_wav_probe.py --usb
python tools\frida_smz_wav_probe.py --usb --code 1049 --output-dir /sdcard/Download/magireco_wav_probe
```

## 外部工具

- Python 3.10+
- FFmpeg，用于视频封装、音频合并、候选拼接
- JADX，用于生成本地 `jadx_audit/base_src_only`
- 可选：`requests`, `tqdm`, `mitmproxy`
- 可选：Frida，用于在模拟器进程内调用 native WAV 转换探针

## 安全原则

默认命令尽量 dry-run。会移动、复制、导出或合并文件的步骤需要显式加 `--execute`。

旧的候选数切片拼合只保留作研究证据。当前生产流程使用
GDB -> Z2D -> DGM -> native CRI 的官方引用链重建事件，并按官方事件根和画布分组生成 B 站分 P。
