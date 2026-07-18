# MagiaReco 动画恢复项目人类可读进度报告

更新时间：2026-07-16（文件名保留首次检查点日期）

本报告面向项目所有者和外部接手者。它回答四个问题：现在真正完成了
什么、游戏机制解明到什么程度、离可投稿长片还差什么、下一步为什么不再是
逐个看 `ac` 文件猜声音和字幕。

静态通用性、字体和 CDN 的逐项证据/限制另见
[`research/2026-07-13-static-generality-font-and-cdn.md`](research/2026-07-13-static-generality-font-and-cdn.md)。

## 一句话结论

项目尚未完成，但也不是只靠肉眼逐个拼视频。资源容器、事件到素材的静态关系、
Direction 宏调度、SP Story 抽奖与 selector、声音 request 到跨线程 CSL PlayStart
的通用骨架已经被解出；ac7116 的尾帧 hold 已在同一次官方强制事件中达到
runtime-mechanism 级证明。当前最关键的缺口，是在同一次**自然目标事件**中闭合
继承的具体外层 BGM、入口 loop phase、音量变化和退出行为，并恢复断电丢失的自然
同源原始审计链。全库批量生产必须等这个门禁可靠，不能再生产“有声音但语义错误”
的假成品。

最终交付规格现固定为 **2 条音频母版 × 3 种字幕 = 6 个发布 edition**：

1. `with_bgm`：BGM + 游戏原生语音/SE；
2. `no_bgm`：不含 BGM，但保留同源语音/SE；
3. 每条音频母版各派生无字幕、日文字幕、中文字幕。

两条母版的语音/SE、画面和时间轴必须一致；BGM 版必须另有曲目 source hash、
request/start、循环相位、原生音量与 ducking 证据。六版都保留原生画面尺寸、帧率
和合理码率等级。旧渲染器使用的 `Yu Gothic` 不是游戏字体证据；静态提取已经证明
故事文字使用 `JM_<Unicode>_<family>_<variant>` DGI/ASTC 字形链，当前日文语料覆盖
完整，但现有字形只覆盖约 8.46% GB2312 汉字。因此日文可走游戏字形；中文现已
独立锁定 Noto Sans CJK 2.004 的固定 commit、SHA-256 与 OFL-1.1 许可证，并实测覆盖
目标三事件候选字符 34/34。它明确标为非游戏原生的可审计中文字体；翻译和布局仍需
人工批准，不能静默回退到本机字体。

## 2026-07-16 最新检查点

- 2026-07-16 存储修正：A: RAMDISK 已关闭，后续不把 A: 当输入、scratch 或输出。
  耐久研究/媒体统一写入 `D:\magia\MyProducts\casino`；C: SSD 保留仓库和小型临时
  文件。旧 manifest 内的 A: 只作为历史 provenance，经显式 path-prefix map 与 source
  hash 核验后解析到 D:，不能恢复成新的 A: 依赖。
- 付费门控已全量映射：只有 7 个 SKU，依次为存档、Wait Cut、设置、Auto、强制役、
  前五项合集、Sound Pack。前六项不增加独占媒体；Sound Pack 是唯一直接影响成片
  音轨的门。固定台设定 1–6 受 index2 门控，但五个角色按钮本身不付费，并会写入
  `g_CustomChara/g_CustomVoice`，后续应作为角色/语音覆盖维度。购买回调没有另一条
  PAD/OBB 下载链。详见 `research/2026-07-16-paid-addon-gates-and-archive-impact.md`。
- 静态变体空间已进一步压缩：免费 `?` 会随机得到有效设定 0..5；固定设定只改变
  普通 Story 的六张概率描述符，目标 SP Story 彩票完全不读设定。五个 UI 角色是
  5 个 profile 而非 5×5 voice，强制役 0..19 也与目标 `(stage,selector)` 不同域。
  因此购买状态变化不会直接加速 ac7114/15/16 自然 BGM 门；后续按 event/video/
  voice/subtitle canonical signature 分等价类，避免 7×5×20 盲跑。详见
  `research/2026-07-16-setting-character-force-variant-space.md`。
- 当前 PID3188 的新版只读 entitlement snapshot 已验证 7/7 active/saved 共 14 个字段
  全为 0，且没有 gameplay input/native call/memory write。capture manifest SHA-256 为
  `FDADCE46BB6252F61356D4662D6696C2857A569294993B071E1A39F3E5E86E15`。
- CDN 于 2026-07-16 复查三个客户端已声明边界对象，仍为 HTTP 200 且大小未变；Android
  客户端、392 分片流量、7,801 视频 inventory 和官网仍没有 HLS/quality/720p/1080p
  或同剧情高清 variant。当前 CDN 可重拉原始 OBB/PAD，但没有隐藏高清母版证据。

- 2026-07-15 的 PID3207 是历史捕获；当前 2026-07-16 连接为 PID3188，ARM64 Gadget
  已恢复且 addon 快照保持零输入/零写入。PID3207 的零输入 journal SHA-256 是
  `68ECC94DF1C3B08C5CD51EAC72636FECBDA0E2CCCF67A9A983C15D34F3585A6D`；222-ID
  Sound Pack 表的 13 个 key check 全部匹配，初始 active rows 为空。这是重连健康
  检查，不是“游戏没有 BGM”的证据。
- 用户确认 BGM 是在此前 PID3125 五局自然 non-target 批次中听到的；ID800 当时
  runtime volume=0，不能贡献可听声音。静态反汇编现已证明 835/836 都由
  `C_ObjNml::fnSndRequest_BGM_DIR()` 直接请求，不再只是“loop=1 的候选”；但零输入
  跟随快照在五局结束约 14 分 35 秒后才开始，仍不能把人的听感唯一绑定到其中一首。
- 新的上游静态链证明 ac7114/15/16 目标对象自身不请求 BGM，而是继承全局 Direction
  `kind/no`：`kind=0x2f` 且 `no=1..24` 选 835，`no>=25` 选 836。当前 `kind/no` 有
  多条提交/恢复/清零 writer，DirInfo 的 190/191/192 是另一套字段，不能拿来推 836。
  因此剩余动态捕获已缩到目标同 run 的 writer/快照/请求/播放器相位，而不是盲目挂
  全部声音。详见 `research/2026-07-15-target-sp-story-bgm-state-upstream.md`。
- 对应 5 个上游 hook 已进入通用 hunter，并在 PID3188 做完 8 秒零输入预检。MuMu 的
  GameProc 是 APK-backed 未压缩映射，因此身份门同时核验已安装 split APK 外层 SHA、
  固定 ZIP entry 内部 ELF SHA/AArch64 header，以及运行时 derived base/export offset；
  成功检查点 13/13 hooks、0 unavailable/error、973 条 sound metadata 零丢失，且
  `adb_input_sent=false`。journal SHA-256 为
  `562A8F16864D6D0377CDC32E3F603338C4133A3DA37F4B5CF96D2204631C0F11`。这证明下次
  自然目标可以直接捕获命名字段，不代表主界面空闲时已确定目标 BGM。
- 首个实际回合暴露并失败关闭了一处高频 signature 溢出；修复为 hook+对象分区并
  排除 call ID 后，可执行回归及第二个单回合均通过。成功的 non-target `_06` 只有
  40 条上游状态（37 DataSet、2 BGM_DIR、1 RlStart），window closed、0 drop/error，
  141 条完整 sound trace，credit 47→44 并回到 0/0。journal SHA-256
  `7D8FA6761DAD9AF55405EC845FB0CB53CB0DF62D59D7CEC4C2234E4A4C84826E`。该回合没有
  `kind=0x2f`/835/836，不冒充目标；它证明真实负载下 observer 已可用。
- 加固的历史 snapshot audit 汇总 32 条 active row，其中 4 条 gate row
  （ID800/801/821）均为零音量；unentitled corroborating/conflict=4/0，invalid=0，
  pre-gate row=0。三份输出 hash 与完整边界见
  `research/2026-07-14-audible-bgm-observation.md`。
- LC701A 已静态闭合 `f070..f075` 六字节到 ED31/DirInfo3 的读取链，并证明
  `CplayData::LoadData` 可覆盖该工作区；自然抽选时的最后 writer 仍未定位。下一步
  需要短时只读 writer probe，见 `research/2026-07-15-lc701a-f070-native-writer.md`。
- 两条真实 audio base-master 的合成器和现代 scene 六版构建器已经落地并通过 tiny
  real-media E2E。事件母版 H.264 stream-copy、AAC 48 kHz stereo、逐包/逐帧 PTS、
  有效 PCM、source rehash、clipping 和 READY transaction 全部失败关闭；scene 不直接
  拼 AAC，而是按每个 sidecar 的 `presentation_sample_count` 裁切有效 PCM，连续拼接后
  每个音频 profile 只编码一次，再复用到 none/JA/ZH 三版。视频 packet、帧格、样本、
  cue、hash 或 READY 任一不一致都会拒绝发布。
- 提交前故障注入进一步修复了发布事务：series 不再直接拼 AAC；scene、subtitle batch、
  material collection 全部在同卷 staging 完成后才 promotion；旧 READY 在失败重跑中
  保持逐字节不变；event audio master 用跨进程 mutex + no-replace hardlink，竞态
  sentinel/foreign replacement 不会被覆盖或回滚删除。material audible 也改成精确
  trim/gain/duck、PCM 连续拼接和最终单次 AAC，并要求 hash-bound 人审视觉语义。
  详见 `research/2026-07-16-release-pipeline-hardening.md`。
- v20 production manifest 已在 D: 实际构建：926 个事件中 521 READY、405 fail-closed；
  ac7114/15/16 的旧 A: provenance 通过显式 path-prefix map 指向已核验 D: 副本，三个
  event 都 READY 且不再含 A: 路径。summary/catalog SHA-256 分别为
  `9025608499EE13760A817CF8DF630AC08EE92F539EF6C13E1E2042835C2A58B2` /
  `6E6D7C01CD98B11704543266D7E523254CBDCE37BA9A2C21CA8FCE90AC06A927`。
- ac7114/15/16 的真实 clean visual 已通过 QA，均为 512x288、30 fps、H.264、无音轨、
  无字幕，精确为 289/666/391 帧；对应 48 kHz presentation grid 是
  462400/1065600/625600 样本。这些是可信画面输入，不是最终投稿成片。仍缺自然目标
  同 run 的 BGM ID/phase/volume/transitions、经人工批准的中文 cue，以及最终游戏布局/
  字体门禁，因此没有把任何旧音频猜测冒充六版。
- ARM64 Gadget 再注入成功后，零输入 preflight 与两批各五局 bounded hunt 均完整；
  十局全部为 non-target、0 overflow、未伪报目标，正常 credit 最后为 19。两个 journal
  SHA-256 为 `6DA701E60A8CD3D5BAB25925C3DFAACC854FA3D6E139E1DB032D5855E7F2ECDE` 和
  `26902C0927129A1E0A7C4BBAD12F857768EA23FE56D8217A14BF41A6DA78436F`。应保留剩余
  credit 做有证据价值的小批捕获，而不是无上限消耗。
- 把 `MAGIRECO_SLOT_ASSET_ROOT` 指向 D: 耐久真实资源后，当前全套自动验证为
  289/289 通过、0 跳过、0 failure/error；四个 installed-asset 字形向量和真实 Noto
  34/34 cmap、FFmpeg 事务/逐样本向量也实际执行。全仓 `compileall`、Frida JS
  `node --check` 与
  `git diff --check` 也通过。
- 提交前独立审查又修掉两处审计风险：每个 modern scene 的 summary/READY 现在独立
  存放，不会被下一个 scene 覆盖；每条 JA/ZH SRT 必须与已审计 `edition_plan` 的 cue
  数量、起止和文本完全一致，合并写出后还会回读逐 cue 校验。音频样本数也改为按
  有理帧率计算，并与 source event manifest、实际帧数和两套 audio sidecar 四方互证，
  不再硬编码 30 fps 的 1600 samples/frame。
- ac7114/15/16 共 10 条日文 cue 已整理成独立中文字幕人工审阅单，但全部仍是
  NOT HUMAN APPROVED。JM 的确只覆盖候选中文 19/34；现在新增的固定 Noto Sans CJK
  2.004 依赖已用真实上游字体覆盖 34/34，并固定字体与 OFL 文本各自的大小和 SHA-256，
  可离线复验且坏缓存默认拒绝覆盖。它是显式 `audited_chinese_fallback`，不是游戏原生
  字体；翻译、字号、描边、安全区和布局获批前仍不具发布资格。依赖说明见
  `../reproducibility/fonts/README.md`，审阅表见
  `review/2026-07-15-ac7114-16-chinese-subtitle-review.md`。

## 2026-07-14 本轮同步推进结果

- 已从原生 `SoundMng::changeVolume@0x425ee68` 只读恢复 Sound Pack **门控前**
  整数音量。自然 non-target 中 ID826 的 class/indexed/master 为 50/100/100，
  authorized final volume=50；当前 entitlement=0 后 CSL runtime volume=0。它证明
  未购买实例仍可用于恢复 BGM 混音参数，而不是停止 BGM 生产。
- 五个 PID3125 journal 的自动 join 捕获 Sound Pack ID800/801/821/826 共 7 个
  proven-playing zero-volume rows，0 个矛盾；旧逐帧 660 条门控前记录已压缩成 5 个
  compact state groups；这些旧记录不能冒充 5 次真实 transition。证据和 hash 见
  `research/2026-07-14-sound-pack-pre-gate-runtime-volume.md`。
- 后续五局自然 non-target 中，用户确认实际听到了 BGM；运行时出现不在 Sound Pack
  表内、volume=50、loop=1 的 ID835/836。静态业务函数现已把两者明确归为
  `BGM_DIR`；剩余问题是单一回合/场景的 exact ID、phase 和 transitions，而不是
  “它们是否为 BGM”。见 `research/2026-07-14-audible-bgm-observation.md` 和
  `research/2026-07-15-bgm-dir-and-csl-cross-thread-identity.md`。
- 2×3 生成合同、真实 audio base-master 合成器、真实 clean-visual 接入和 scene 六路
  连续音频构建器已经落地；证据不完整时拒绝渲染。voice/SE 与 BGM 均需逐源 hash、
  原生 timing/volume，BGM 另需 phase/loop/ducking transitions。日中字幕共用已验证
  cue 时间轴和 placement/safe-area profile，但各自绑定独立字体/hash/cmap；中文允许
  使用完整、可审计的不同字体。现在的剩余阻塞是目标场景的真实 BGM 合同、中文字幕
  审阅和目标媒体六版 E2E，而不是 scene concat 引擎。详见
  `research/2026-07-14-two-audio-master-six-edition-contract.md`。
- ac0906 与 ac0912 的纯素材**视觉分类**成立；ac7204 的源 manifests 有 27 个角色
  语音事件，当前集合折成 14 个唯一 AV 代表、4 个唯一 OGG，必须归为 gameplay/
  result animation review，不能再叫 pure material。旧 audible collection 未验证
  原生 volume/ducking，也没有完整逐 OGG hash，只能保留为 review，不能发布。
- ac1102/ac1103/ac1104 的旧 review 文件、长片时间轴和输出 hash 完整，但 37 条中
  35 条仍缺运行时 AV 验证；ac1103_006/_012/_013 混入胜利粒子/WIN 效果，不能把
  旧系列直接晋升为正常动画长片。2026-07-15 只读迁移 rehash 实查 120 个 family
  source/output 文件，0 missing、0 hash error；这是“文件完整”，不等于“语义可发布”。
  原始 review 保留，不重编码。
- ac0906 material collection 的 schema-v2 清单另核验 36 个引用文件，0 error；仍是
  六个黑幕小 Kyubey 观众素材组件、16 条音频证据，分类
  `reviewed_audience_components_not_standalone_animation` 正确。旧 audible mix 缺当前
  原生 volume/duck/hash/READY 合同，所以可审计但不是当前发布母版。
- 自然 hunt 累计又完成 19 个 bounded non-target 回合，没有伪报 target；最新五局
  将正常游戏 credit 从 18 变为 5，未写 credit 或强制 selector。当前最有价值
  的下一次命中必须在同一 run 绑定 ID19+ID24、精确事件码、BGM request/phase/
  pre-gate volume、语音、字幕和 CSL 最终 transport。

## 静态分析并没有被放弃

目前采用的是“静态机制为骨架、动态运行时为裁决”的混合证据路线。

| 层级 | 当前结论 | 能否跨事件复用 |
| --- | --- | --- |
| APK/PAD/OBB 与 CRI 容器 | 下载、分片、校验、解包和 CRI 索引已可外部复现 | 是 |
| GDB -> Z2D -> DGM -> CRI | 已静态提取事件、画布、图层与原生媒体引用 | 资源身份通用；图层父子和区间尚有可审计启发式 |
| Direction 调度 | `pre -> PlayTableData -> PlayMacroData -> Macro_* -> scene/sound request` 已定位 | 是，属于通用调度骨架 |
| SP Story 选择 | ID19 permission、同批 ID24 stage/selector、精确 event code 和五张 lottery 表已解出 | 对 SP Story family 通用，不等于所有玩法共用同一 selector 表 |
| 声音请求 | request/code/resource/final sound-id 与跨线程 pending-row/PlayStart 已精确接通；835/836 有 BGM_DIR 业务正证 | transport 层通用；其他业务代码、phase/fade/duck 仍需证据 |
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
- 各玩法上游 BGM 状态、入口 loop phase、fade/duck 参数与已闭合 CSL 播放身份的
  同 run 连接；
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

## 2×3 发布矩阵的新增审计要求

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
- 日文和中文共用 cue 时间轴、位置和安全区；两种语言允许使用不同字体，每个字体
  都必须记录 path/hash/family/source/license 并通过各自全文 cmap，中文完整覆盖优先；
- 如果游戏使用预渲染位图字而不是可复用字体，必须先还原字形/排版机制，不能把
  `Yu Gothic` 假称为游戏字体；
- 每条音频母版内部的无字幕/日文/中文三版音频 packet hash 必须一致，字幕烧录只
  允许重编码视频流；`with_bgm` 与 `no_bgm` 两条母版的音频 hash 必须不同；
- 六版画面尺寸、帧率、像素格式和总时间轴必须一致，不做 upscale。

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
本检查点为 289/289 通过（包含真实 JM DGI、Noto cmap、FFmpeg 事务向量、发布后回滚与
输出路径越界向量）。本报告和同批工具会随
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
2. 以已经通过的 ac7116 原生 hold 规则重建三事件 2×3 六版本；
3. 完成 Z2D 字形排版 metrics、逐句中文翻译与人工审校；
4. 对两条母版分别运行三种字幕派生的音频、字幕、画面、时间轴、codec/profile/
   bitrate/audio-hash QA，并由人类完整播放确认。同一母版内三版音频必须同源、
   同时间轴、同 packet hash；两个母版之间只允许 BGM 层不同，且不得 upscale。

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
5. 目标命中后重建 ac7114/15/16 的 2×3 六版本和长版，再进入 catalog 批量阶段。
