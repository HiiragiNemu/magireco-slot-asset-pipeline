# MagiaReco 动画恢复项目人类可读进度报告

更新时间：2026-07-14（文件名保留首次检查点日期）

本报告面向项目所有者和外部接手者。它回答四个问题：现在真正完成了
什么、游戏机制解明到什么程度、离可投稿长片还差什么、下一步为什么不再是
逐个看 `ac` 文件猜声音和字幕。

静态通用性、字体和 CDN 的逐项证据/限制另见
[`research/2026-07-13-static-generality-font-and-cdn.md`](research/2026-07-13-static-generality-font-and-cdn.md)。

## 一句话结论

项目尚未完成，但也不是只靠肉眼逐个拼视频。资源容器、事件到素材的静态关系、
Direction 宏调度、SP Story 抽奖与 selector、声音 request 到 CSL transport 的
大部分骨架已经被解出；ac7116 的尾帧 hold 已在同一次官方强制事件中达到
runtime-mechanism 级证明。当前最关键的缺口是把通用声音层在同一次**自然目标事件**
中闭合继承的外层 BGM，并恢复断电丢失的自然同源原始审计链。全库批量生产必须等
这个门禁可靠，不能再生产“有声音但语义错误”的假成品。

最终交付规格现固定为三种同时间轴版本：

1. 无字幕版；
2. 日文字幕版；
3. 中文字幕版。

三版必须保留原生画面尺寸、帧率和合理码率等级，音轨内容与时间轴必须一致；
日文和中文使用同一套经确认的游戏字体或游戏文字渲染风格。当前旧渲染器使用的
`Yu Gothic` 尚未被证明是游戏字体，所以**字体门禁尚未完成**，不能把现有字体
默认值当作最终规范。

## 静态分析并没有被放弃

目前采用的是“静态机制为骨架、动态运行时为裁决”的混合证据路线。

| 层级 | 当前结论 | 能否跨事件复用 |
| --- | --- | --- |
| APK/PAD/OBB 与 CRI 容器 | 下载、分片、校验、解包和 CRI 索引已可外部复现 | 是 |
| GDB -> Z2D -> DGM -> CRI | 已静态提取事件、画布、图层与原生媒体引用 | 资源身份通用；图层父子和区间尚有可审计启发式 |
| Direction 调度 | `pre -> PlayTableData -> PlayMacroData -> Macro_* -> scene/sound request` 已定位 | 是，属于通用调度骨架 |
| SP Story 选择 | ID19 permission、同批 ID24 stage/selector、精确 event code 和五张 lottery 表已解出 | 对 SP Story family 通用，不等于所有玩法共用同一 selector 表 |
| 声音请求 | request/code/resource/final sound-id 静态表与低噪声运行时链已接通 | transport 层通用；BGM/对白等业务语义仍需证据 |
| 字幕 | 官方图形文字、声音标签、运行时字幕及其时间可进入 manifest | 日文来源层部分通用；中文翻译与字体尚未实现 |
| 外部合成 | composition plan、单事件渲染、系列 stream-copy、QA/哈希/时间轴工具已存在 | 引擎通用；尚不能自动决定所有多层事件的观众语义 |

当前静态路由解码规模为 290 个 DirInfoTable entry、9,732 个 EventInfo；926 个
manifest 事件目前覆盖 3,908 条可追溯 route row。这证明“kind/row/selector ->
event code”是表驱动机制，但不证明每条路由的最终声音、尾帧和图层观众语义已经
全部闭合。

这说明游戏本身并不是“人工逐个分类每个 ac”。它通过表、事件码、宏和对象状态
驱动播放。项目过去需要人工 composition plan，是因为还没有把所有游戏内决策表
和图层语义完整转成外部声明式计划；这些 plan 应当逐步退化为少量例外适配器，
而不是长期成为 926 个事件的手工主流程。

现在还不能声称“全部事件调度已完全非黑盒化”。以下环节仍未闭合：

- 当前部分 Z2D DGM interval/parent 解析仍使用有界邻近与媒体时长匹配；它可输出
  证据位置，但还不是完整 Z2D 语法解释器；
- 外部 compositor 尚未完整复刻 DGI/shader/nameplate 等渲染能力；
- 从所有玩法的上游状态到完整 Direction sequence 的统一外部解释器；
- ZG play-info 与 CSL active transport 的身份等价及 BGM 业务语义；
- ac7116 已证明 end-frame 337 在 voice tail 持续可绘；跨事件的 LP/影片结束/尾帧
  通用状态规则仍未形式化；
- 所有图形字幕和角色语音的自动、唯一、可复核关联；
- 游戏字体/字形图集如何被调用，以及中文字幕需要的汉字覆盖范围。

因此动态调试当前不是替代静态分析，而是用来验证静态解释器是否真的复现了游戏
同一条路径。最终目标仍是让绝大多数事件由通用 manifest builder 自动产生，只把
无法由表意确定的观众取舍交给人工复核。

## 2026-07-14 MuMu 重连与三局小批检查点

MuMu 重启后的新前台 PID 为 `3125`。x86 Frida server 可直接看到进程，但其
`Process.arch=x64`，无法解析 ARM64 `CSlotBody`/`CReel` 导出；这次直接 attach 的
失败已保留，且没有发送输入：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260714\evidence\natural_hunter_pid3125_server_readonly_smoke_20260714_01
hunt_journal.jsonl SHA-256
76024DABC98C089D9EC18C13D71079DAEE90E1EC405EF2D5711C29694356F887
```

随后只通过现有 x86 attach surface 重新加载 ARM64 Gadget，没有重启游戏、没有
发送玩法输入。reinject summary SHA-256：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260714\evidence\gadget_reinject_pid3125_20260714_01
179E136AF6E2B5B1DC0C90691F1F625C3D48CDD46F68CAA57DE7BF2BCB653AC5
```

ARM64 只读 smoke 随后成功：65/65 个 CSL slot 全部捕获、`truncated=false`，开始和
结束均无 active row，`adb_input_sent=false`。journal SHA-256：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260714\evidence\natural_hunter_pid3125_gadget_readonly_smoke_20260714_01
E7BA647DDFBC8B166478367B53669D7786EBE4247DB4A442AAD9C661D4A941C1
```

接着只跑了 3 局有上限的小批自然 hunt：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260714\evidence\natural_hunter_pid3125_active_csl_execute_20260714_01
hunt_journal.jsonl SHA-256
5A1D45FEF85D9EE706907172FFE7229FEBD592B43DF1F8FE7B572804EB3E6E6C
```

| attempt | 用时 | 动作 | dispatch | event codes | observer bytes | 结果 |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 3.934 s | 5/5 | 7 | 22 | 219,826 | non-target |
| 2 | 4.013 s | 5/5 | 7 | 10 | 241,076 | non-target |
| 3 | 3.898 s | 5/5 | 7 | 10 | 243,141 | non-target |

每局三轴均为 0/1/2、无 overflow；ID19 均为 `19 0 2 0 0 1 0 22`，不是 SP Story
permission，因此没有合法 target。ID304 在三局 post snapshot 都继续存在，说明它是
值得追踪的跨局 transport，但在 ZG identity 与 Sound Pack entitlement 闭合前仍只能
标为候选，不能叫 BGM。

### Sound Pack 混杂因素已经从疑问变成确定门禁

当前 PID 3125 的只读快照证明七个 addon saved/active 标志全部为 0，尤其索引 6
Sound Pack 没有解锁。`SoundMng::changeVolume` 和 `checkEnableSoundID` 会在索引 6
为 0 时扫描一张 222 项声音 ID 表，通用 `play -> sndPlayReq -> wrapSndReq` 和 channel
路径都会先经过该音量门禁。当前 BGM/SE/Voice 均为 50、master 100，Android 媒体
音量也未静音，所以这不是普通音量设置造成的。

只读状态日志：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260714\evidence\addon_state_pid3125_readonly_20260714_02
capture_manifest.json SHA-256
5932A15AF90BAA831B9EE2C7C08A4ADE077C4823C4567A81DC2D4214F694C89F
```

222 项中 219 项能精确连接到当前 `sound_id_records.csv`，绝大部分是长音轨；资源在
OnDemand SMZ 中已经存在，未购买时由 native gate 静音。ac7114/15/16 的局部 420xx
故事声音不在该表，但它们仍可能继承进入事件前已经播放的 outer BGM。因此当前无声
捕获不能证明场景原生无 BGM，也不能授权外部猜配。完整反汇编、表统计和最小合法
A/B 方案见
[`research/2026-07-14-sound-pack-entitlement-gate.md`](research/2026-07-14-sound-pack-entitlement-gate.md)。

## 2026-07-13 运行时检查点（历史但仍有效）

本次确认游戏仍在前台，包名为 `com.universal777.magireco`，最近一次有效捕获 PID
为 `3083`。PID 只是一份 dated evidence；MuMu 重启后必须重新读取，任何报告都
不得把旧 PID 当永久地址。

有效 reinject 证据：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260713\evidence\gadget_reinject_pid3083_20260713_01
gadget_reinject_summary.json SHA-256
DA752417710EF91EFDE6B28F7EACA79E65B5215A1AC97AF35100453AEAAE924F
```

Houdini 把 ARM64 游戏映射物理登记为 `split_config.arm64_v8a.apk`，所以当前探针从
游戏专有导出反查所属映射，不再依赖显示名必须为 `libGameProc.so`。

最新只读 smoke：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260713\evidence\natural_hunter_pid3083_active_csl_readonly_smoke_20260713_03
hunt_journal.jsonl SHA-256
DA92840BC7E140AF1EF8A25E6BA77F97133E36ECA06BE375DDB666BE31F1A6CB
```

该 smoke 没有发送 gameplay 输入。CSL active vector 声明 65 个 slot，捕获 65 个，
`truncated=false`，开始和结束均无 occupied/playing/pending/paused row；每次 RPC 只在
下一次 `CSLMng::Calc` 所在线程快照，然后立即 detach。128 是防御性捕获上限，不是
游戏声明的 slot 数量。

已有的一次普通自然局 `_execute_20260713_01` 捕获到 4 个正在播放的 transport row，
但每一行都明确保留 `bgm_semantics_proven=false`。其中 ID 820 静态映射到一条伊吕波
对白，这反证了“channel 1 或 loop flag 就一定是 BGM”。ID 304/resource 834 和
ID 308/resource 839 的源 OGG 分别约 58.46 秒和 14.29 秒，但没有业务标签，仍不能
仅凭长度或听感晋升为 BGM。

本次又完成 3 次小批自然局：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260713\evidence\natural_hunter_pid3083_active_csl_execute_20260713_02
hunt_journal.jsonl SHA-256
16B2929BD3FF6B6137AD29CF245F7708AA76D762024B1E11E572C77B581BD828
```

| attempt | 用时 | 动作 | dispatch batch | 结果 | observer bytes |
| ---: | ---: | ---: | ---: | --- | ---: |
| 1 | 4.080 s | 5/5 单次接受 | 7 | non-target | 294,015 |
| 2 | 3.990 s | 5/5 单次接受 | 7 | non-target | 248,265 |
| 3 | 3.780 s | 5/5 单次接受 | 7 | non-target | 217,540 |

每局左/中/右 `setStopAngle` 轴均为 0/1/2，expected/observed progress 均依次为
`0x200000 / 0x600000 / 0xe00000`，无 buffer overflow。三局 ID19 仍是
`raw[1]=0, raw[2]=8`，不是目标 permission；没有合法同批 target，也没有精确
ac7114/ac7115/ac7116 event code，因此 3 次 `target_hit=false` 均为正确保守结论。

## 最近可观看但尚未晋升正式投稿的场景

ac7114/ac7115/ac7116 的日文字幕/无字幕单事件与 44.854 秒同场景长版目前是最近的
候选。D 盘长版仍存在：

```text
D:\MagiReco_Reverse\magireco_verified_scenes_v19_clean_audio_gate_20260628\ac7114_16_sp_story_clean_audio_gate
```

其中有独立 `scene_manifest.json`、`scene_index.csv`、两套 ffconcat、SRT、
无字幕 MP4 和日文字幕 MP4。它们可以供人类验证已知的语音和字幕，但仍不是最终
投稿版，原因是：

1. 还未在自然目标路径中证明外层 BGM/bed 的完整状态；
2. 断电后缺少自然目标同源原始日志重捕；现有 hold 的机制命题本身已经通过；
3. JM 字形导出/缺字门禁已实现，但中文字幕逐句翻译、Z2D 排版 metrics 与人工审校
   尚未完成；
4. 当前 v19 是 libx264 重编码，约 1.09--1.11 Mb/s，低于现有主故事源约 1.506
   Mb/s，且只有两版；它不能称为原生码流/同等级码率的最终投稿文件。

ac7116 的机制证据来自同一次强制事件：`ac7116_AT_SP_story5_01.dgm` 为 512x288、
0..337 帧；11.267--13.05 秒尾段仍有 42 次 `ExecPlayMovie`、168 次
`IsDrawTime/GetDecodeFrame`、28 次 decode 和 20 次 drawCall，输入/解码帧保持 337，
`IsDrawTime(337)=1`。权威报告已在 commit `27aeb1b` 固化为
[`research/2026-07-02-ac7116-renderer-texture-state-probe.md`](research/2026-07-02-ac7116-renderer-texture-state-probe.md)。
原始 7 月 3 日 A 盘 JSONL 已随断电丢失，所以自然目标重捕仍有审计价值，但不应
再次把“hold 是否原生”列为未知。

这里新增一个重要限定：官方[应用发布公告](https://www.universal-777.co.jp/news/20260415002485/)
和 [Google Play 页面](https://play.google.com/store/apps/details?id=com.universal777.magireco)
都说明单独的 Sound Pack 会解锁主要通常时 BGM 和 bonus music。当前安装中存在
OnDemand SMZ 只能证明声音资产在设备上，不能证明当前账号 entitlement、游戏设置
和 native 播放门禁已开启。现在又已直接证明当前七项 addon 均为 0，并定位索引 6
控制的 222-ID 静音表。因此“这一局没听到 BGM”既不能证明事件原生无 BGM，也不能
授权外部随意补曲；必须同时记录 Sound Pack/音量状态与真实 PLAY/STOP 链。

## 三版本字幕的新增审计要求

正式 production manifest 每个 cue 至少要保留：

```text
event, cue_id, start_ms, end_ms,
ja_text, ja_source, ja_source_hash,
zh_text, translation_status, reviewer,
font_source, layout_profile, evidence
```

约束如下：

- 日文必须来自游戏图形文字、官方运行时文字或可追溯声音标签；ASR 只能辅助审校；
- 中文必须逐句对应同一个日文 cue，并保留人工复核状态；机器翻译不能直接进入正式版；
- 日文和中文使用同一字体来源、字号逻辑、描边、位置和安全区；
- 如果游戏使用预渲染位图字而不是可复用字体，必须先还原字形/排版机制，不能把
  `Yu Gothic` 假称为游戏字体；
- 三版音频 hash 必须一致，字幕烧录只允许重编码视频流；
- 三版画面尺寸、帧率、像素格式和总时间轴必须一致，不做 upscale。

### 游戏字体审计结论

旧脚本的 `Yu Gothic` 只是仓库默认值，提交历史没有给出 APK、运行时或官方字体
来源；它必须继续标记为 provisional。对 base APK、ABI/密度/语言 split 和
InstallTimePack 的归档条目检查没有发现 TTF、OTF、TTC、FNT、WOFF 或独立 font
目录，`split_config.zh.apk` 也只有 Android 资源和签名文件，不提供中文字形。

进一步静态解码已经纠正了早期候选：`utf8_font_package.bin`、
`sjis_font_package.bin`、`hankaku.dgi`、`zenkaku_*.dgi` 属于当前安装中缺失且被禁用的
debug-print 路径，不是故事字幕字库。真实故事路径是 DGI archive 内 4,124 个
`JM_<Unicode>_<family>_<variant>` 位图字形；原生名表 5,785 项与 `dgi_add.bin` 的
5,786 个边界构成精确一一映射。Z2D 的 49,308 次 JM 引用、4,120 个独立文件名全部
可解析，没有 dangling reference；现有 2,031 条独立日文文本使用的 1,053 个非空格
码点也全部有字形。

游戏内另有两条文字能力，但不能混淆：

1. 故事 `CZ2DString::SetString` 会依次设置 JM glyph 与 authored placement，然后
   设置完整台词；DMP payload 是 ASTC 4x4 的 52x52/56x56 字形纹理，但 DGI header
   不含 advance、bearing 或 baseline，排版 metrics 仍须从 Z2D transform/anchor 解出；
2. `libAMAIN` 的 `CDrawRes::SetFont -> DrawMng.FontBmpCreate` 使用 Android `Paint`
   和 `Canvas.drawText` 临时建立 bitmap atlas，但没有设置 Typeface，因此只是系统
   默认字体路径，尚未证明故事字幕使用它。

`zg::sprite::Renderer` 另有 font-file API，但默认路径为空，现有运行日志也没有捕获
实际故事字幕 draw 调用。JM 集合是游戏语料专用：只覆盖约 15.13% 的 Shift-JIS
双字节 repertoire、约 8.46% 的 GB2312 CJK，不能覆盖任意中文字幕。正式中文必须
逐码点 coverage gate；缺字时采用明确披露、带 hash 的中文 fallback，并保持游戏
排版风格，不能静默回退到 Yu Gothic，更不能把 fallback 假称为官方游戏字形。

## CDN/更高分辨率路线：存在研究价值，但尚无高分母版证据

`D:\magia\videodownloader.py` 属于完全不同的 Magia Exedra。它只提供一种方法论：
从客户端 config/manifest 发现真实视频路径，再请求官方 playlist；其 Akamai token、
AES、M3U8 和 `Movie/...` 命名不能套用到 slot。

slot 客户端自己的静态证据显示另一套下载机制：

```text
SERVER_URL = http://app.universal-777-res.com/magireco/
main.<version>.com.universal777.magireco.obb_<chunk>.obb.jar
patch.<version>.com.universal777.magireco.obb_<chunk>.obb.jar
```

客户端自定义的 OBB 资源版本 `latestVerCode=9`（不是 APK versionCode；当前 APK 是
versionCode 31 / versionName 1.0.0）的分片 CRC/长度表直接编译在 `ResCRC`，客户端
按表下载、校验并合成 OBB。静态表精确声明 main 217 块、3,411,813,224 bytes，patch 175 块、
2,746,538,910 bytes；本地流量捕获的 784 条 universal 请求正好是这 392 块各一次
HEAD 和 GET。当前 D 盘 OBB、安装导出与 reference-input hash/size 一致，并已解出
`cri.bin/cri2.bin`。PAD 只声明 `OnDemandPack01`，安装导出中该 pack 是 SMZ 音频；
InstallTimePack 才包含 DGI/GDB/OGG/PCM/Z2D 等资产。

2026-07-13 只对客户端清单内三个已知对象做了精确 HEAD（没有目录枚举或盲扫）：
`main_0001`、`main_0217`、`patch_0175` 均返回 200，长度分别为 15,728,640、
14,426,984、9,755,550 bytes，说明当前清单端点仍在线。Android 包、两个 OBB 和
OnDemand SMZ 合计约 7.143 GB（十进制），与 Google Play 对首启大容量下载的说明
相符。

客户端通用数组还列出可选名 `cri3.bin/cri3_add.bin`，但当前唯一声明的
`OnDemandPack01`、安装导出、URL/CRC 清单都没有该实体，游戏也可在没有 cri3 的
情况下运行。因此它只能记作通用或遗留槽位，不能据此臆测存在缺失高清包。

官方产品页、数字指南和应用发布公告的页面源码只见静态图片、商店链接及官方频道
入口，本次没有发现 `.mp4`、`.m3u8`、`.webm` 或 playlist。iOS 是独立包，后续可在
合法取得安装包和初启流量的前提下做有限平台对照，但目前也没有 iOS 使用更高分辨率
动画的证据。

这条 CDN 路线真实存在，但当前证据只证明能重新获得客户端声明的完整资源。APK、
流量和对象列表中都没有发现 M3U8、playlist、quality 档位、720/1080 或平台变体。
现有动画 inventory 的故事主画面通常为 416x232；512x416/512x288 条目常是不同
屏幕/图层，不能当作同一故事视频的高清替代。因此“同一 slot CDN 另藏未引用高清
母版”目前只是待证假设，不是已有发现。

接下来只做客户端证据可导出的验证：版本清单、PAD pack、历史版本、同一资源的
明确平台/质量变体和官网公开宣传源。若找到更高分辨率官网视频，会标为“官网宣传
源”，不会伪装成游戏运行时原生文件；若客户端 catalog 和官方对象只给 416x232，
则最终投稿也保持这个原生尺寸，绝不 upscale。

## GitHub 状态与截图中的红叉

截图里失败的是另一个仓库 `HiiragiNemu/ma-ex-dataSP` 的定时工作流。经 GitHub
CLI 核验，本项目仓库是：

```text
HiiragiNemu/magireco-slot-asset-pipeline
default branch: codex/corrected-runtime-pipeline
```

本项目目前只启用 GitHub `Dependency Graph`，最近一次运行成功；HEAD 没有配置
commit check。GitHub API 的 `pending` 且 `total_count=0` 表示没有 check run，
不是 CI 测试失败。设置版本匹配的 `MAGIRECO_SLOT_ASSET_ROOT` 后，本地全套测试在
本检查点为 113/113 通过（包含真实 JM DGI 向量）。本报告和同批工具会随
本轮提交直接推送到唯一工作分支；GitHub 页面只会在 push 完成后显示它们。

## 距离最终目标还有多少

不能用一个虚假的百分比表示，因为可靠性门禁是串联的。926-event inventory 为：

| 门禁 | 数量 |
| --- | ---: |
| technical-ready | 521 / 926 |
| ready 且已有单事件 QA | 304 / 521 |
| ready 但缺单事件 QA | 217 |
| ready 已进入 preserved/series set | 267 / 521 |
| ready 仍缺 series decision | 254 |
| material/excluded 已收集 | 82 / 405 |
| material collection 尚缺 | 323 |
| 严格 AV 证据门禁阻断 | 897 / 926 |

对“第一组真正可信的 B 站长片”而言，还差四个硬阶段：

1. 自然命中 ac7114/15/16，闭合 packet/event/voice/outer-audio，并把原始证据直接
   持久化到 D 盘；
2. 以已经通过的 ac7116 原生 hold 规则重建三事件三版本；
3. 完成 Z2D 字形排版 metrics、逐句中文翻译与人工审校；
4. 运行三版音频、字幕、画面、时间轴、codec/profile/bitrate/audio-hash QA，并由
   人类完整播放确认。无字幕/日文/中文三版可以因烧录字幕使用不同视频编码，但音频
   必须同源、同时间轴、可核对 hash，且不得 upscale。

对“全部资源归档”而言，之后仍有 catalog 级规模化生产：217 个单事件 QA、254 个
系列决定、323 个素材合集以及大量严格 AV 证据。当前最重要的进展不是多生成几百
个文件夹，而是已经把过去导致错误音频/字幕的猜测路线换成可失败关闭的通用机制
门禁；一旦首个自然目标闭合，才能安全把同一规则扩展到全库。

## 下一步执行顺序

1. 将 ZG published play-info 或等价官方 active identity 接入当前 CSL snapshot，
   不再用 channel/loop 猜 BGM；
2. 继续小批自然 SP Story hunt，只在合法同批 target 时保留完整 observer 包；
3. 同时完成静态通用机制边界、游戏字体和 slot CDN/PAD 的三份审计；
4. 更新核心 handoff/status，运行全套测试，提交并推送正确分支；
5. 目标命中后重建 ac7114/15/16 三版本和长版，再进入 catalog 批量阶段。
