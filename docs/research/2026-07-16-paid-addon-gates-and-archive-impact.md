# 2026-07-16 付费 addon 门控与动画归档影响

## 结论摘要

客户端只有 7 个一次性 Google Play `inapp` SKU：
`magireco_addon_01` 至 `magireco_addon_07`，没有隐藏第八项或订阅。它们映射为：

| index | 商品 | 对归档内容的影响 |
| ---: | --- | --- |
| 0 | Save Data | 只影响保存/恢复，非媒体门 |
| 1 | Wait Cut | 只改变转轮等待时间，非媒体门 |
| 2 | Settings Change | 允许固定选择台设定 1–6，间接改变概率/覆盖效率 |
| 3 | Auto Play | 自动 lever/stop，非媒体门 |
| 4 | Forced Role | 可主动改变小役/bonus flag 和部分 lottery route，影响取证效率 |
| 5 | Value Pack | index 0–4 的合集，没有独立内容；不含 Sound Pack |
| 6 | Sound Pack | 唯一直接改变最终音轨可听内容的门，控制 222 个声音 ID |

官方发布公告逐项描述 Save、Wait Cut、Setting、Auto、Force、Sound Pack；Google Play
还明确写明 Value Pack 不含 Sound Pack。原生 `SetAddonID` 对 index 5 的特殊行为与此
一致：它写 0..5，但不写 index 6。

本轮仅静态分析和读取既有快照，没有调用购买接口、写 entitlement 或发送 MuMu 输入。
归档路线继续从本地已分发资源、门控前参数和官方调度证据外部复刻媒体。

## 版本与状态布局

```text
libGameProc.so
size 79683640 bytes
SHA-256 5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF

libAMAIN.so
SHA-256 58E3F7A9DBCE2E3D79D1A5A30F1DBFEEAC5BB4712BD4D8FF4E6328D2631DCA5D
```

`CplayData::SetAddonID(int,int,bool)@0x421b4d4` 使用两组连续 u32：

| index | active offset | saved offset | label |
| ---: | ---: | ---: | --- |
| 0 | `+0x14bf4` | `+0x14a58` | Save Data |
| 1 | `+0x14bf8` | `+0x14a5c` | Wait Cut |
| 2 | `+0x14bfc` | `+0x14a60` | Settings Change |
| 3 | `+0x14c00` | `+0x14a64` | Auto Play |
| 4 | `+0x14c04` | `+0x14a68` | Forced Role |
| 5 | `+0x14c08` | `+0x14a6c` | Value Pack |
| 6 | `+0x14c0c` | `+0x14a70` | Sound Pack |

scene 保存的 entitlement 指针指向 `CplayData+0x14b6c`，以上 active 字段相对该指针
为 `+0x88/+0x8c/+0x90/+0x94/+0x98/+0x9c/+0xa0`。`SetAddonID` 从
`0x421b64c` 起对 Value Pack 做批量写入：index 5 为 1 时把 0..5 设为 1，但不触碰
index 6，因此 index 5 不是另一种玩法或媒体门。

历史只读快照：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260714\evidence\addon_state_pid3125_readonly_20260714_02
```

该 dated PID3125 快照的 7 项 active/saved 均为 0。它证明当时实例未购，不代表当前
进程状态；当前工具仍须按 PID/架构/二进制 hash 失败关闭后重新读取。

### 2026-07-16 当前 PID3188 只读复核

ARM64 Gadget 已在不重启游戏、不发送 UI 输入的前提下恢复。首次 reinject summary 因
host 端尚未 `adb forward tcp:27043` 而正确写成 `ok=false`，但其注入输出和设备 `ss`
已经显示 Gadget loaded/listening；该失败 summary 不冒充成功。补 forward 后的独立
诊断结论为 `runtime_capture_ready_via_arm64_gadget`：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260716\evidence\runtime_state_pid3188_post_forward_20260716_01\runtime_capture_state.json
SHA-256 A6EE5A58C0FA76A3FE72AE2A984EFC4D2E705A73CE3F0434246F8CE7AF5D0C28
```

新版带 SKU/label/impact 元数据的只读 entitlement capture：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260716\evidence\addon_state_pid3188_readonly_20260716_01
capture_manifest.json             FDADCE46BB6252F61356D4662D6696C2857A569294993B071E1A39F3E5E86E15
addon_entitlement_snapshot.json   39D5300F73F907BF6AF75B78F227B1ABBC9B62CB20D2156B013E0A4A9C223C68
probe_messages.jsonl              330F338CB140117423C7D8ADF7DE5B27E500397268350604361ED8CBB8CC3AB9
```

该次 PID3188、ARM64、7/7 active/saved 共 14 个字段读取成功，所有值仍为 0；
`gameplay_input_sent=false`、`memory_write_performed=false`、
`native_function_called=false`、`entitlement_modified=false`。

## 各门控的 native 行为

### index 0 — Save Data

- `CScnSlot::initButton@0x423c164`：`0x423c404..0x423c410` 读取 `+0x88`，写入
  slot `+0x48`；
- `CScnSlot::touch_Interrupt@0x423d5cc` 使用该字段门控中断/保存 UI；
- `CScnTitleSmu::Calc@0x4245e18` 读取 `+0x88`，未开时在 `0x4245edc` 弹购买提示。

它不选事件、画面、声音或资源。对项目的价值是断点恢复和长时间采集便利；项目自身的
D: manifest/evidence/device backup 仍是更可靠的断电恢复链。

### index 1 — Wait Cut

- `CScnSlot` constructor `0x42409f4` 读取 `+0x8c`；未开时
  `0x4240a04/0x4240a08` 强制普通 wait；
- `CplayData::IsFastAutoMode@0x421b494`；
- `CSlotBody::calcReelWait@0x4250d6c`；
- `CSlotBody::autoWaitCheck@0x42520b8`。

它只改变转轮/Auto 的等待节奏，不改变媒体资产或事件映射。若用加速模式取证，必须把
wait mode 写入 provenance，不能把外层加速间隔当成动画原生时间轴。

### index 2 — Settings Change 与角色按钮

`CScnTitleSmu` constructor `0x4244f2c..0x4244f44` 保存 entitlement 指针。
`CScnTitleSmu::Calc`：

- `0x4245c3c/0x4245c44` 读取 `+0x90`；
- 确认按钮 0..5（台设定 1..6）时，`0x4245ddc..0x4245df4` 在值为 0 时弹购买提示；
- 按钮 6 的随机 `?` 不经过这项购买门；
- 角色按钮 7..11 的 `0x4245c80..0x4245cc8` 及
  `checkCharBtn@0x424619c` 不读取 `+0x90`。

因此用户截图中的五名角色不是付费角色包。开始模拟时台设定写入 CplayData 子结构
`+0x4c`；角色写入 `g_CustomChara@0x4c202c4` / `g_CustomVoice@0x4c202c8`
（`0x4245ef8..0x4245f1c`）。台设定会改变概率分布，角色可能改变角色/voice 变体；
归档 manifest 应保存 setting/character 维度，但未购实例仍可用 `?` 与五个角色。

### index 3 — Auto Play

- `CScnSlot::autoStart@0x42362bc`；
- `autoCount@0x42362dc`；
- `autoPlayChk@0x42364ac`；
- `touch_AutoOn@0x423c5c0` 读取 `+0x94`，未开时
  `0x423c64c..0x423c668` 弹购买提示；
- `drawMenuBar@0x4238264..0x4238280` 负责灰显。

它只自动 lever/stop 和结束条件，不解锁事件、声音或资源。外部有界输入 hunter 已能
承担同类运行工作，并保留每步 acceptance/waterline/provenance。

### index 4 — Forced Role

- `touch_Force@0x423c768` 在 `0x423c78c` 读取 `+0x98`；未开时
  `0x423c890..0x423c8ac` 弹购买提示；
- `CScnSlot::addonForceSelectExecute@0x4235af0` 取得 `CForceWindow` 的 0..19 选择；
- `onStartInit@0x423a11c` 在 `0x423a230` 取选择并于 `0x423a23c` 调
  `CSlotBody::setForceMainFlag@0x4253d04`，写 body `+0x520`。

这是除 Sound Pack 外对动态覆盖效率影响最大的一项，因为它会改 lottery/event route。
但 forced flag 不等于完整上游状态或最终 event identity；已有 0..19 映射也没有直接
命中 ac7114/15/16 的通用 SP Story selector。任何 forced capture 都要显式标注，不能
当作自然概率或自然 outer-BGM 证明。更高效的主线仍是静态解码
ID401/SdGmData/DirInfo/EventInfo，再做极少量官方运行时验证。

### index 6 — Sound Pack

`SoundMng::changeVolume@0x425ee68` 与
`SoundMng::checkEnableSoundID@0x425efc0` 读取 `CplayData+0x14c0c`。为 0 时对
`libGameProc.so+0x14458dc` 的 222 个严格递增唯一 sound ID 实施静音/禁用。
219/222 已连接当前本地 sound records；它不门控画面、字幕和 420xx 剧情语音，但会
影响通常时/bonus music 以及进入剧情时可能继承的外层 BGM。

这是唯一必须在最终 `with_bgm` 母版中复刻的付费内容门。所需证据仍是业务 request、
源 hash、门控前原生整数音量、loop phase、fade/duck/PLAY/STOP/CSL，而不是仅看购买
标志或凭听感猜曲。

## Billing 与资源交付是两条链

Java/smali 证据：

- `util/AddonID.java` / `AddonID.smali` 只出现 7 个 SKU；
- `Addon.java` 的业务代码是 app 内唯一 BillingClient 购买/恢复调用方；
- 查询恢复会先把 7 个 active 清零，只在 `purchaseState==1` 且 SKU 精确匹配时调用
  `JniBridge.getAddonID(index,1,true)`；离线则从 native saved menu data 恢复；
- 所有购买/恢复路径都没有调用 `ResourceDownload`、`DLAsset` 或 AssetPackManager。

资源侧：

- `InstallTimePack` 在 manifest 中明确为 `<dist:install-time/>`；
- Java 只声明一个 `OnDemandPack01`，属于启动资源完整性流程；
- entitlement 全 0 时，本机已经存在 `OnDemandPack01/smz.bin`
  152,226,304 bytes 与 `smz_add.bin` 39,012 bytes；
- PID3125 的 ID826 已证明原始 48 kHz stereo OGG 存在、门控前 volume=50，随后被
  index 6 清零。

所以目前没有“购买后才下载角色/剧情/动画/声音包”的证据；Sound Pack 是预置资源的
运行时播放门。其余 addon 是行为控制门。

所谓“6 个 missing SMZ”也已进一步降级：它们是连续 request 32–37 / code 171–176
的六条 213.018/215.000 秒长轨，request 38/code 177 只是把六个 ReqData 组合起来。
`sound_id_records.csv` 对 171–176 均有安装态 OGG chunk 33..38，request audit 时长与
hash-request duration 精确相等；ID171–177 也不在 Sound Pack 222-ID 门表。缺的是 SMZ
name-table hash 指向的后端对象，不是逻辑声音载荷。这支持“遗留/替代后端引用”，不
支持“购买后另下载内容”。该复合长轨为何保留 SMZ 名仍属后端格式解释项。

三个曾标 `unmapped` 的 gate ID 也已分类：

- 9070/9071 是复合 cue，不应按“单一 direct OGG resource ID”查找。request2066
  `9070_CC_コネクト導入_クロエ` 组合 9060/9061；request2067
  `9071_CC_コネクト導入_ほむら` 组合 9060/9062 及控制/marker。三条子声音均有本地
  SMZ/OGG：`snd_09060...09852.ogg`、`snd_09061...09853.ogg`、
  `snd_09062...09854.ogg`，时长 5.000/3.467/3.467 s；
- 863 在当前 request/code-name/sound record/event timeline 中没有可达业务 cue。邻近
  856–862/865 有 direct record；数字相同的 request_id863 和 OGG chunk863 属于其他
  编号域。稳妥分类为当前版本 stale/reserved orphan，不是缺失下载包证据。

因此所有原 `unmapped` 项均未指向付费增量媒体：两个是载荷完整的复合 cue，一个是
当前不可达的保留表项。

## 对目标和工作量的实际判断

| 项目 | 若有该功能的加速 | 是否改变最终内容正确性 |
| --- | --- | --- |
| Save | 便于断点续跑 | 否 |
| Wait Cut | 提高 spin 吞吐 | 否；还会改变外层时间 provenance |
| Settings | 更快覆盖特定概率表 | 间接；需记录 setting，但资源不新增 |
| Auto | 提高跑量 | 否 |
| Forced Role | 快速触发部分稀有分支 | 会改变调度来源，不能替代自然 BGM 证据 |
| Sound Pack | 便于门控前后 A/B 听检 | 是，最终 with-BGM 必须外部复刻其官方调度 |

因此付费控制能减少动态等待，但不解决当前最难的因果门禁：ac7114/15/16 仍需一次
自然目标，把全局 Direction kind/no、835/836 或继承状态、入口 phase 和同帧
fade/stop/duck 连接起来。强制役即使触发相似画面，也不能把 forced outer state 冒充
自然入口。

## CDN/高清路线的最终当前结论

2026-07-16 对客户端已声明的 revision-9 边界对象重新 HEAD：main 0001、main 0217、
patch 0175 都仍为 HTTP 200，Content-Length 与历史清单完全一致。客户端固定根只有：

```text
http://app.universal-777-res.com/magireco/
main.9.com.universal777.magireco.obb_NNNN.obb.jar
patch.9.com.universal777.magireco.obb_NNNN.obb.jar
```

历史 392 HEAD + 392 GET 已覆盖声明对象，合并 hash/size 与安装态一致；客户端、流量、
7,801-video inventory 和官网均未发现 HLS/m3u8、720p/1080p quality tier、同剧情高清
variant 或另一条 master 路径。官方 Google Play 仍写首启约 7.5 GB，正好与现有
APK/OBB/PAD 规模吻合；官方公告也只列 addon 功能，没有高清媒体下载说明。

当前结论是：Android Slot CDN 可用于可审计地重拉已声明原始资源，但不是已发现的
隐藏高清动画 CDN。现有 416x232/512x288 等是客户端原生媒体尺寸；512x416 等通常是
不同画面/图层，不是同一动画的高清版。CDN 继续低成本监测新 resource revision、
明确 quality 字段和合法 iOS 包差异，但主线仍是原生尺寸外部 AV 复刻，不做 upscale。

## 已收口与后续动作

只读 addon snapshot 已带精确 index/label/impact；request32..38 与原 `unmapped` gate ID
也已在上文分类。`setting × character × force` 的进一步静态枚举已经完成，证明免费
随机设定覆盖有效 0..5、固定设定不进入目标 SP Story 彩票、五角色是 5 个 profile 而
非 5×5、force 0..19 与目标 `(stage,selector)` 不同域。完整表见
`2026-07-16-setting-character-force-variant-space.md`。

仍需：

1. 自然命中目标时闭合 BGM ID/phase/volume/fade/duck/stop；
2. 把 OBB/PAD/source hashes 与上述异常统一进入 distribution manifest；
3. 低频监测新的官方 resource revision 或明确 quality 字段，不做无边界 URL 猜测。

官方说明：

- https://www.universal-777.co.jp/news/20260415002485/
- https://play.google.com/store/apps/details?id=com.universal777.magireco
