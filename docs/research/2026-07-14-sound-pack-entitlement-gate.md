# 2026-07-14 Sound Pack entitlement 与原生静音门禁

本报告回答一个会直接污染 BGM 结论的问题：当前 MuMu 中“没有听到 BGM”，究竟
能否证明事件原生没有 BGM。结论是**不能**。当前账号/运行态没有 Sound Pack
entitlement，游戏会在通用声音请求路径中把固定声音集合的音量强制变为零。

本轮只读检查没有购买追加包、没有改写 entitlement/config、没有给游戏发送输入，
也没有把表内曲目擅自补进任何成片。

## 1. 官方产品语义

[Google Play 官方页面](https://play.google.com/store/apps/details?hl=ja&id=com.universal777.magireco)
说明另售 Sound Pack 会解锁主要通常时 BGM 和 bonus 中的权利乐曲；同页还明确
お買い得パック不包含 Sound Pack。官方
[应用发布公告](https://www.universal-777.co.jp/news/20260415002485/) 也把 Sound Pack
列为独立商品。因此安装了声音数据不等于账号获得播放权限。

Java 客户端的 `util/AddonID.java` 按顺序声明
`magireco_addon_01` 到 `magireco_addon_07`。`util/Addon.java` 和
`util/Addon$3.smali` 会先清零七项，仅在 Google Play purchase state 有效且 SKU
匹配时把对应索引传给 `JniBridge.getAddonID(index, 1, true)`。SharedPreferences 中
没有另一份 entitlement 或音量替代状态。

## 2. native entitlement 状态

版本匹配的 `libGameProc.so`：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\native_analysis\libGameProc.so
SHA-256 5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF
```

`CplayData::SetAddonID` 位于 `0x421b4d4`。七项 active 值从对象偏移 `0x14bf4`
开始，七项 saved 值从 `0x14a58` 开始；索引 6 因而分别是 `0x14c0c` 和
`0x14a70`。value-pack 分支只会设置索引 0..5，不会设置索引 6，这与官方“value
pack 不含 Sound Pack”的说明一致。

当前 PID 3125 的 provenance-complete 只读 ARM64 快照显示 saved/active 七项全部为
0。探针没有读取或声称另一项 purchased flag。证据包同时记录前后台 PID、package/
version、ARM64 module/base/path、实例导出与偏移、探针/驱动/lib hash，并明确零输入、
零 native call、零 memory write：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260714\evidence\addon_state_pid3125_readonly_20260714_02
capture_manifest.json SHA-256
5932A15AF90BAA831B9EE2C7C08A4ADE077C4823C4567A81DC2D4214F694C89F
addon_entitlement_snapshot.json SHA-256
0011E38977B49ADDD4CDDE23345CB97728DC411A7630F88B9BB6A0A7D3B7ED4C
```

所以当前实例的索引 6 门禁没有开启。该证据包只描述 2026-07-14 的当前实例；PID、
module base 和绝对地址不得跨重启复用。

## 3. 222 项原生静音表

`SoundMng::changeVolume@0x425ee68` 读取 `CplayData+0x14c0c`。值为 0 时，它扫描
`libGameProc.so` 文件/VMA 偏移 `0x14458dc`、长度 `0x378` 的 32-bit ID 表；命中后
把本次请求的音量乘数清零，再继续 `SndSetVol`。
`SoundMng::checkEnableSoundID@0x425efc0` 读取同一门禁和同一张表，未解锁且命中时
返回 false。

这不是孤立的菜单检查。通用播放调用链为：

```text
SoundMng::play(int,int) entry 0x42601c8
  call-site 0x4260384 (+0x1bc) -> sndPlayReq entry 0x425fbdc
  call-site 0x425fde4 (+0x208) -> wrapSndReq entry 0x425f09c
  call-site 0x425f15c (+0x0c0) -> changeVolume entry 0x425ee68
  call-site 0x425f190 (+0x0f4) -> SndReq

buffer play overload entry 0x4260464
channel wrapper entry 0x425f254
  call-site 0x425f318 (+0x0c4) -> changeVolume
  call-site 0x425f340 (+0x0ec) -> SndReqCh
```

入口地址和函数内 call-site 必须保持区分；旧的 `0x4260360`、`0x425fddc`、
`0x425f13c`、`0x425f30c` 是内部 basic block/call-site，不是这些函数的入口。

表中正好 222 个递增且唯一的声音 ID，范围 67..41032。与版本匹配的
`asset_manifests/sound_id_records.csv` 精确连接 219 项：218 项在 bank 01，一项在
bank 08；未连接的只有 863、9070、9071。后两项的静态标签分别是
`CC_コネクト導入_クロエ`、`CC_コネクト導入_ほむら`。版本匹配媒体审计中，219 项
里 176 项至少 10 秒、95 项至少 30 秒、48 项至少 60 秒；例如 ID 171 约
213.019 秒，ID 778/786 约 264.467 秒。这证明门禁集合包含大量长音乐资源，但不
允许把每个 ID 都不经业务证据地命名为某一场景 BGM。

该表可由
[`extract_sound_pack_gate.py`](../../tools/frida_runtime_probe/extract_sound_pack_gate.py)
只读重建。工具输出 lib/table hash、逐项 ID、精确 CSV 源行、bank/时长/未映射统计，
并把 symbol entry 与 call-site 分列；它只描述版本限定门禁，明确禁止用这些偏移写入
entitlement 或绕过购买。v31 table fingerprint 不匹配时默认退出 4 且不生成文件；
只有显式 `--allow-unmatched-reference` 才能生成标为 `experimental`、`ok=false` 的研究
输出。当前运行态快照则由
[`capture_addon_entitlement_state.py`](../../tools/frida_runtime_probe/capture_addon_entitlement_state.py)
与无调用/无写入的 `addon_entitlement_state_probe.js` 生成。

当前静态工具的 D 盘重建结果：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260714\evidence\sound_pack_gate_static_v31_20260714_02
sound_pack_gate.json SHA-256
1F884E522ECCB462E57BEE2137F139B601C383E87718F65B627C4DF9A43D98E1
sound_pack_gate.csv SHA-256
54F675A6F98175F42414D61A7EFC9326118B48CEBABF2BBB1C48BA07824BF433
```

OnDemandPack01 中 `smz.bin`（152,226,304 bytes）和 `smz_add.bin`（39,012
bytes）在 entitlement 为 0 时也完整存在。购买行为看来是放行预置资源，不是另下
一套高清或独立媒体包。

## 4. 已排除普通音量设置

当前 `SoundMng` 运行态的 BGM/SE/Voice 三档均为 50，master 为 100；构造函数默认
也是 50/50/50 和 100。Android `STREAM_MUSIC` 为 100/100，系统 mute/internal
mute 均为 false。因此当前缺失的受门禁曲目不能归因于游戏菜单音量或系统媒体静音。

## 5. 对 ac7114/ac7115/ac7116 的精确限制

`event_timeline_sounds.csv` 给出的事件局部声音为：

- ac7114：42040..42051；
- ac7115：42060..42069；
- ac7116：42080..42093；
- 另有 255/242/257 一类停止命令和 8040 金带 SE。

这些 420xx 故事声音不在最大值为 41032 的 222 项 Sound Pack 表里。因此已确认的
对白/字幕正确性不因这张表被否定；但目标场景可能继承“进入事件前已经开始播放”的
outer BGM。只审计事件局部清单，既不能证明有 outer BGM，也不能证明没有。

最小可靠验证顺序固定为：

1. 不改 entitlement，在进入目标场景前后只读记录真实 `SoundMng` request ID、
   PLAY/STOP、ZG identity 和最终 CSL transport；
2. 若请求了 222 表内 ID 而最终音量为零，就能证明当前未购买门禁导致该曲静音；
3. 最强 A/B 只能由用户合法购买 Sound Pack 或切换到合法已购账号后，在同一路径
   确认 active index 6 为 1，再重复只读捕获；
4. 在上述证据前，不伪造 entitlement、不猜配曲、不把无声运行晋升成“原生无
   BGM”。

这项修正把过去的笼统疑问变成了可测门禁，但尚未替代 ac7114/15/16 同一次自然
目标事件的入口前后声音捕获。
