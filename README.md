# Magireco Slot Asset Pipeline

基于游戏静态代码、资源引用和运行时证据，还原 MagiaReco Slot 的动画、对白、音效与字幕，
形成**原生分辨率、内容穷尽且不重复的场景长片／素材合集**。

这不是仅按文件名拼接视频的工具，也不以逐局触发全部演出为目标。代码分析用于确定内容全集、
分支、层级和调度规则；有限动态采样用于验证仍有疑问的时序与参数。

## 当前状态 · 2026-10-03

- 唯一开发及默认分支：`codex/corrected-runtime-pipeline`。本项目不另开分支或 PR。
- 最新代码整合基线：[70b925c](https://github.com/HiiragiNemu/magireco-slot-asset-pipeline/commit/70b925c7d1e90e18113bb6a4ed67299f7eab7afb)，
  已纳入此前 112 项代码、测试、计划与文档积压，并修正历史输入绑定及 Git 换行导致的哈希风险。
- 该基线全仓回归：**1013 通过、4 跳过、0 失败**。这是代码测试结果，不是人工播放批准。
- 已有静态内容全集盘点、event-global 音画调度、分层／循环／尾帧分析、精确去重和长片构建流程；
  **全项目尚未穷尽完成**。已提交 ac0001–ac0005 等后续长片计划，仍需与集中审查索引逐项衔接。
- 现存原生 416 集中审查批次为 **20 个内容组、48 个语言／伴随版本文件**，状态
  `HUMAN_PLAYBACK_REQUIRED`。这是一个已发布审查批次，不是全项目库存总数，也不是 48 部独立作品。
- P16／ac6003、P17／ac6004、P18／ac6005，以及未闭合的 child-local → event-global 时序继续隔离。
  旧 v24/v25 的 QA、旧 READY 数字或历史人工批准不能自动外推到后续重建版本。

详细状态以 [PROJECT_STATUS](docs/PROJECT_STATUS.md) 顶部为准；
整合范围与原始资源保留理由见 [2026-10-03 整合记录](docs/research/2026-10-03-backlog-integration-and-source-retention.md)。

## 内容与验收标准

1. **穷尽独立内容，而非累加文件数量。** 同一场景／剧情的入口、选项、互斥结果均需纳入覆盖表。
   互斥分支可按可理解的顺序整合为一部长片，但不冒充游戏原生单局；同一内容只出现一次，
   保留其所有事件／来源映射。音频、字幕或有效画面不同的版本不应误判成重复。
2. **长片优先。** 事件短片用于来源、QA 和复现，不默认作为独立剧情产品交付。
   分离路线版须有项目所有者的具体需求；纯素材按其真实组件用途保留，不因短或叠加后才可见而丢弃。
3. **原生画布。** 优先 416×232 的 Slot 演出；512×288 等较低优先级记录后排队。
   不 upscale，不按尺寸强行拉伸或机械拼接；多层组件必须有 composition plan。
4. **音画字幕证据。** 层区间、父子实例化偏移、循环、尾帧、对白、SE、字幕和累计时间轴必须对应。
   child Z2D 的局部帧号不等于父事件全局时间；缺少依据时保持阻断，不靠目测统一平移。
5. **语言与音频轨分开管理。** 剧情按实际内容提供 NONE／JA／ZH；无语言差异的纯视觉／无声素材
   只保留一个无语言后缀的文件，不制造三份 `__none`／`__ja`／`__zh` 包装。
   同哈希审查一次，确需跨目标使用时以可追溯别名处理。
6. **人工批准绑定精确文件。** 自动 QA、人工播放通过、可投稿、已投稿、隔离是不同状态；
   批准必须绑定具体文件和 SHA-256，不因同 family 或相同字幕轨名称而扩展。

### no-BGM 与 with-BGM

- **no-BGM**：有意排除 BGM，保留已证明的对白与 SE。使用代码导出的音频总线／请求身份，
  不把未知声音猜成 SE，也不声称游戏原本无 BGM。
- **with-BGM**：独立证据门控轨。曲目身份、入口相位、音量、fade／duck／stop、来源哈希和
  事件／路线时间线闭合后再进入正式生产，不用猜测音轨填补缺口。
- 保持原生分辨率与合理码率，交付视频 30 fps、H.264；有声输出使用 AAC 48 kHz stereo。
  无声纯素材不为凑规格添加无意义语言音轨。

### 人物身份与翻译

黑羽（黒羽）、黑（黒）、黑江（黒江）是三个角色。`speaker_code=kuro` 有上下文歧义，
不得全局映射；`kuroe` 是黑江。使用
[精确身份覆盖表](tools/frida_runtime_probe/speaker_identity_overrides_v1.json)，未闭合的 `kuro` 不加人物名前缀。
黑江及八千代对环彩羽的对应「環さん」称呼按已确认规则译为“环同学”。

## 人工审查入口（本地 D:）

稳定指针：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\manual_review_hub_v2_flat\CURRENT_NATIVE416_EXHAUSTIVE.json
```

截至本页更新，指向：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\manual_review_hub_v2_flat\releases\native416_exhaustive_new_standard_v144_20260824
```

从该目录的 `00_START_HERE.md` 开始，再按 `ZH`／`JP`／`NONE` 查看 `story`、`routes`、
`gameplay_effect`；纯素材集中在 `MATERIAL`。MP4 平铺，不要求人类逐个进入 family/event 目录。
该批次使用同盘 NTFS 硬链接，不另复制媒体。`JP` 是目录显示名，对应计划中的 `ja`。

以上 20 组仍是待审候选，不是投稿目录。GitHub 不携带这些本地视频，克隆仓库不会获得成片。
旧 `CURRENT_PRODUCTION.json`、`00_BILIBILI_统一入口`、分散版本目录及七月分 P 数字只保留来源意义，
不应与本页入口混用。新增内容先更新绑定清单与统一索引，不另造零碎人类审查入口。

## 仓库与本地数据的边界

| 保存位置 | 内容 |
| --- | --- |
| Git / GitHub | 分析与构建脚本、测试、轻量研究文档、composition / production plans、精确覆盖和来源指纹 |
| D: 原始资源目录 | 官方 APK／OBB、CRI、native SO、解包表与源媒体；不作为 Git 大文件上传 |
| D: 版本化研究／生产根 | runtime 证据、manifest、QA、原始单事件及候选成片；保留来源关系与隔离状态 |
| D: 集中审查入口 | 按当前索引聚合的硬链接视图；不是又一份物理媒体备份 |

本机工作树：

```text
D:\Codex\State\worktrees\2fe8\com.universal777.magireco-Ga9DaxEd9F9Lqn9OVKVSfw==
```

旧主目录仍包含原始输入和共享 `.git`，不是可整体删除的过时仓库。
旧拼接成片／分类结论可以失去当前权威性，但原始 OBB／CRI／SO 不因目录日期早而失效。
A: RAMDISK 不作为当前输入、生产或证据保存位置。不自动创建整仓／整盘备份，也不自动上传 Bilibili。

## 开发与复现

先看 [输入与复现指南](reproducibility/README.md) 和
[核心交接](docs/HANDOFF_NEXT_AI_MAGIRECO.md)，确认具体计划、源指纹和隔离边界。
[字体依赖](reproducibility/fonts/README.md) 独立锁定；本地字体缓存不是无用媒体副本。
历史工具链锁和输入指纹是对应检查点的记录，不应覆盖当前已经验证的环境。

在已配置依赖的工作树中运行全仓回归：

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
python -B -m unittest
```

生产实现及探针位于 [tools/frida_runtime_probe](tools/frida_runtime_probe/)。
运行时操作只验证静态预测的具体问题；先核对 Slot 的 exact-hash SO／IDA 会话和实际进程，
使用 ADB 确认的数字 PID、单会话、不显式 unload 的策略。旧 `--usb`／进程枚举／双会话示例
不作为当前操作入口，也不操作其他正在运行的游戏。

## 研究导航与历史边界

- [ac0908 全入口／结局代码权威复核](docs/research/2026-08-24-ac0908-exhaustive-authority-after-reverse.md)
- [ac1102 旧长片与新内容全集复核](docs/research/2026-08-24-ac1102-legacy-longform-code-authority.md)
- [ac7205 代码权威与长片重建](docs/research/2026-08-24-ac7205-code-authority-and-v150-production.md)
- [原生 416 静态来源全集构建器](tools/frida_runtime_probe/build_native416_static_source_universe.py)
- [ac0005 穷尽去重长片计划](tools/frida_runtime_probe/series_proposals/exhaustive_unique_longform_ac0005_v252_20260824.json)
- [研究记录目录](docs/research/)

带日期的报告保留其当时观察，不因本页更新而重写成今天的结论。
旧 `main_video_NNNN_candidatesX` 拼接、motion/static 分类、1080p upscale、旧全局人物映射，
以及早期 `NEXT_STEPS`／`OFFICIAL_EVENT_PIPELINE`／`BILIBILI_PRODUCTION_WORKFLOW` 的命令
均不作为当前生产指令。需要复现历史实验时，应使用该检查点的完整来源合同，而不是从旧说明中摘一条命令直接运行。
