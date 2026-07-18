# 2026-07-15 BGM_DIR 业务语义与 CSL 跨线程身份链

本记录关闭两个此前分开的缺口：

1. 运行时反复出现的声音代码 `835` / `836` 到底是不是 BGM；
2. `SoundMng::sndPlayReq` 发出的请求怎样在另一个线程上与
   `CSLMng::PlayStart` 的最终播放对象做无歧义连接。

结论是：`835` / `836` 已由 `libGameProc.so` 的业务函数直接证明为
`BGM_DIR` 请求；底层播放身份则可用 CSL 表行指针和 pending slot 做精确的跨线程
join。这个结论不依赖画面相似、时间邻近、channel 编号或文件名猜测。

## 静态版本锚点

```text
libGameProc.so
SHA-256 5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF

libAMAIN.so
SHA-256 58E3F7A9DBCE2E3D79D1A5A30F1DBFEEAC5BB4712BD4D8FF4E6328D2631DCA5D
```

所有地址均为对应 ELF 的 module-relative offset，不能直接套用到另一版二进制。
运行时 probe 会核对实际 module offset；不匹配时主要 hook 失败关闭。

## 835 / 836 的业务语义已经静态闭合

`C_ObjNml::fnCtrlSnd` 在 `0x43a2358..0x43a235c` 的每个控制周期调用
`C_ObjNml::fnSndRequest_BGM_DIR()`。后者位于 `0x43a86b0`。当
`[this+0xca] == 0x2f` 时：

- `0x43a8bb4` 读取 `[this+0x11a]`；
- 值为 `1..24` 时选择字符串 `"835"`（字符串地址 `0x11dd780`，使用点
  `0x43a8bd0/0x43a8bd4`）；
- 值大于等于 `25` 时选择字符串 `"836"`（字符串地址 `0x133978e`，使用点
  `0x43a9140/0x43a9144`）；
- 选中的代码写入 `[this+0x800]`；
- `0x43a9854..0x43a9860` 只在代码变化时调用
  `C_CtrlSndLib::fnReqSndSoundCode(code, 1)`。

因此这里的 `835` / `836` 不是“根据时长和 loop flag 猜出的候选”，而是游戏
`BGM_DIR` 状态机自己生成的 sound code。仍需区分各层编号：

| 业务 sound code | RequestCtrl request index | `sound_id_records.csv` record | sound resource ID | OGG chunk |
| ---: | ---: | ---: | ---: | ---: |
| 835 | 362 | 304 | 835 | 305 |
| 836 | 363 | 305 | 836 | 306 |

对应原始媒体为：

| sound resource ID | 原始 OGG | 时长 | 格式 | SHA-256 |
| ---: | --- | ---: | --- | --- |
| 835 | `snd_00835_bank01_ogg_00305.ogg` | 13.090896 s | Vorbis 48 kHz stereo | `7F399D88E10387983C2C60785AB83ED7812275B280459A65D31C5322A50C8416` |
| 836 | `snd_00836_bank01_ogg_00306.ogg` | 10.991771 s | Vorbis 48 kHz stereo | `5C57130F5E9A9DE5416458AEDFFB91EB4E2CA5203323B7EE6CC88DBCDDC9F8E4` |

RequestCtrl 的相关 reqdata 位置分别为 `0xeda8` / `0xee50`；对应 request
table row 起点为 `0xed60` / `0xee08`。这里记录这些位置是为了版本复核，生产
manifest 仍必须保存业务 code、request index、sound resource ID、OGG chunk 和
source hash，不能把任意两层编号当作天然相等。

作为强度对照，静态资源表还能闭合 800/814/821 的编号映射，但本轮没有找到与
835/836 相同等级的 `.text` 业务函数直接引用：

| business/resource code | request index | `sound_id.dat` record | final OGG ID | 时长 |
| ---: | ---: | ---: | ---: | ---: |
| 800 | 335 | 277 | 278 | 16.581 s |
| 814 | 344 | 286 | 287 | 16.000 s |
| 821 | 349 | 291 | 292 | 24.419 s |

800/814/821 的字符串位于间接数据对象/表结构；存在完整映射不等于已证明业务角色。
所以 ID800 的门控后零音量是运行时事实，ID814 的外层 BGM 说法仍是候选，不能把
这些结论提升到 835/836 的 `BGM_DIR` 静态强度。

## 835 / 836 production mix 的 ReqData、循环、音量和切换语义

本节使用的原始 request table 是：

```text
unpacked_assets/assets/zg_snd_request_tbl.bin
SHA-256 0CDDEBFD9AF8DF233F221D8D42E92839ED46899C7307007C8B0E72044C827513
```

835 / 836 分别是 request index 362 / 363；两行的 serialized ReqData 除 own ID
外完全相同。与 production mix 直接相关的字段是：

| serialized field | 835 / 836 value | 已闭合语义 |
| --- | ---: | --- |
| `u32_00..01` | `0, 0` | 64-bit channel 0 |
| `u32_02` | `1` | function type `PLAY` |
| `u32_05` | `1` | master-volume index 1 |
| `u32_06..09` | `0x01000100` each | 八个 16-bit command volume 均为 256，即 unity |
| `u32_18` | `0x00010002` | `format=2 SMZ, chain=0, loop=1` |
| `u32_19` | `0` | seek time 0 |
| `u32_20` | `362` / `363` | own request ID |
| `u32_21` | `0xffffffff` | no target request ID |
| `u32_22` | `0` | fade attr `NONE` |
| `u32_23` | `0` | duck attr `NONE` |

两行的 `marker_count=0`，也没有独立 fade/duck extra record。这里的结构解释不是
根据数值模式猜测：

- `zg::snd::ReqData::convert@0x4288a00` 在 `0x4288a14..0x4288a78`
  复制公共 `0x28` bytes，然后把 source `+0x28` 交给
  `PlayReq::convert@0x4289830`；
- `PlayReq::convert` 在 `0x42899b4..0x42899c0` 把 source `+0x20/+0x24`
  分别写入 converted PlayReq `+0x18/+0x1c`，所以 serialized `u32_18/19`
  最终位于 converted ReqData `+0x40/+0x44`；
- `RequestCtrl::dbgPrintReqTblReqData@0x428727c` 在 `0x4287334` 读取
  `+0x40` format byte，在 `0x4287344` 读取 `+0x41` chain byte，在
  `0x4287348` 读取 `+0x42` loop u16，在 `0x4287350` 读取 `+0x44`
  seek u32；其打印格式串位于 `0xf71554`；
- format 相对字符串表 `0x14523dc` 明确给出 `0=NONE, 1=PCM, 2=SMZ`；
  function-type 表 `0x14523a4` 给出 `1=PLAY`；fade 表 `0x14523e8` 和
  duck 表 `0x14523fc` 均给出 `0=NONE`。

因此 little-endian `0x00010002` 的解释是已证明字段布局，而不是一个仍待命名的
`reqdata_flag`。

### `loop=1` 是整个 SMZ 媒体从头重开，直到被停止或替换

游戏一般性地支持 SMZ 媒体头中的独立 loop start/end，但 835 / 836 的请求明确
不使用它：

- `DecoderSmz::open@0x4269b20` 在 `0x4269d30` 读取 decoder
  `+0x28/+0x2c` 的媒体内嵌 loop start/end；
- `0x4269d50` 读取 PlayReq `+0x1a` 的 loop u16。有效媒体 loop 区间存在而
  request loop 非零时，`0x4269d80..0x4269d84` 把区间长度置零，并用
  `str xzr, [decoder,#0x28]` 同时清除 start/end；
- 只有保留了内嵌区间，`0x426a0a8..0x426a0c4` 才会设置 decoder
  `+0x7f20` 的 loop-marker flag。对应 accessor 是
  `DecoderSmz::isLoopMarker@0x426aa4c` 和
  `getLoopMarkerStartSmpl@0x426aa58`；
- `PlayerImpl::sndOpen@0x428336c` 在 `0x42833b4..0x42833c8` 把
  ReqOrder `+0x70` 的 PlayReq 交给 decoder，并在
  `0x4283494..0x42834a0` 把 ReqOrder `+0x88` 的 packed PlayReq 保存到
  PlayerImpl `+0x98`；故 PlayerImpl `+0x9a` 是同一个 loop u16；
- 正常游戏播放路径中，`PlayerImpl::sndDecode@0x428168c` 到达媒体 EOF 后，
  `0x42818a8` 先检查内嵌 marker；无 marker 时，`0x42818b0..0x42818b8`
  检查 PlayerImpl `+0x9a == 1`，满足即在 `0x42818e4..0x4281910`
  调 decoder `reopen`。该字段不递减，所以会持续循环，直到收到 stop/replace；
- `DecoderSmz::reopen@0x426a64c` 在 `0x426a660..0x426a670` 要求 marker
  flag 和 marker start 同时非零才进入 marker seek；否则转到
  `0x426a6e4` 的正常流首重开路径。

所以 835 / 836 的 production 语义是“各自整首媒体从头无限循环，直至游戏停止或
换曲”，不是请求表中的一段 loop interval，也不是把若干短音频顺序 concat。内部
`util::isCaptureEnable()` 的特殊 capture 分支会绕过通常的 EOF loop 判断；最终实机
证据仍应在正常玩法 run 中直接看到 `DecoderSmz::reopen`，不能把工具 capture 模式
与正常游戏播放混为一谈。

### native volume 50 的最终增益是 0.5，即约 -6.02 dB

对于已观察到的 835 / 836 native chain，class/indexed/master volume 是
`50/100/100`。`SoundMng::changeVolume(int,int)@0x425ee68` 的整数路径为：

```text
stage = floor(class_volume * indexed_volume / 100)
native_final = floor(stage * master_volume / 100)
```

`0x425ef44..0x425ef5c` 最终把 `native_final=50` 送入
`CSndMng::SndSetVol`。libAMAIN 的后续换算为：

- `CSLMng::SndSetVol@0x13066c` 在 `0x1306b0` 保存 int volume，并在
  `0x1306b8..0x1306c4` 调当前 `CSound::SetVolume`；
- `CSLNormal::SetVolume@0x131b74`、`CSLSound::SetVolume@0x1340d8` 和
  `CSLStream::SetVolume@0x135040` 都把非负 int 写到 `CSound+0x28`，再调用
  vtable `+0xb8` 的 `CSound::GetVolNow`；
- `CSound::GetVolNow@0x13646c` 计算
  `float(volume_int * fade_gain_int) / 10000.0`；
- `CSound::CSound@0x1362d8` 从 `0xab590` 装入 `(100,100,0,0)` 到
  `CSound+0x08`，所以没有活动 fade 时 `fade_gain_int=100`；
- 因此 `50 * 100 / 10000 = 0.5`；
- `CSLVolume::SetVolumeF@0x13565c` 在 `0x13569c..0x1356ac` 对
  `0.01 < gain < 1` 计算 `trunc(2000 * log10(gain))`。`gain=0.5` 得到
  `-602` millibel，即约 `-6.02 dB`。该函数对 `gain>=1` 输出 0，对
  `gain<=0.01` 输出 `-16000` millibel。

这证明的是无额外 mute/fade 时的起始 gain。后续全局音量、显式 fade 或 duck 仍可
改变实机混音，所以 manifest 不能只写一个静态 `volume=50` 而省略 transition
时间线。

### 835 与 836 的自身切换是 STOP 后 open，不自带 crossfade/duck

`PlayerImpl::performRequest@0x4282a3c` 在 `0x4282a68` 从 ReqOrder
`+0x50` 读取 function type；type 1 的 `PLAY` 分支从 `0x4282aa0` 开始。旧声源
仍 active/status 有效时：

1. `0x4282af0..0x4282afc` 调 `PlayerImpl::sndStop(false,false)`；
2. `0x4282b2c..0x4282b38` 才调 `PlayerImpl::sndOpen`；
3. open 成功后，`0x4282b40..0x4282b54` reset `FadeCtrl` 和
   `DuckingCtrl`。

`PlayerImpl::sndStop@0x4282538` 在 `0x42825a0..0x42825c0` 停 decoder
并清状态；如旧请求原来带 duck，`0x42825c8..0x4282628` 会 release；随后
`0x4282654` 调 `SndStop`，`0x428265c..0x4282664` reset player。835 / 836
均为 channel 0、`PLAY`、fade attr `NONE`、duck attr `NONE`，且没有 extra
record。PLAY 成功后的 duck 设置只在 ReqOrder `+0x9c == 2` 时从
`0x4283180` 进入；本两条为 0，会跳过。显式 fade 则走另一 function branch
`0x4282ea8`，在 `0x4282f18` 调 `FadeCtrl::request`。

`C_ObjNml::fnSndRequest_BGM_DIR` 自身的尾部 `0x43a97e0..0x43a9868` 只在
code pointer 变化时调用 `fnReqSndSoundCode(code,1)`，没有直接调用 fade helper。
由此可以证明：**835/836 两条 request 自身不编码 crossfade 或 duck；若旧曲仍活跃，
默认 replacement 是 STOP 后 open。** 但静态二进制仍不能排除另一个业务函数在同一
切换帧前后另发 `VOL_EFCT`、`SET_DUCKING` 或 `RST_DUCKING`；旧曲若已经结束，也
不能声称当时存在可听的 STOP 边界。

### 剩余最小 runtime hook 边界

不需要继续扩大为全库 hook。一次目标事件 run 中保留以下最小因果集合即可：

1. `zgSndReqCode@0x4273058`：记录业务 code `835/836` 与单调时间；
2. `PlayerImpl::performRequest@0x4282a3c`：记录 x0 PlayerImpl 和 x2 ReqOrder
   的 `+0x50` function type、`+0x88` packed PlayReq、`+0x98` fade attr、
   `+0x9c` duck attr。同一 PlayerImpl 时间线必须同时检查 type 4
   `VOL_EFCT`、type 9 `SET_DUCKING`、type 10 `RST_DUCKING`，才能排除外部
   transition；
3. `PlayerImpl::sndStop@0x4282538` 与 `sndOpen@0x428336c`：证明实际发生的
   replacement 顺序和 open 结果，而不是只根据静态可达分支宣称发生；
4. `DecoderSmz::reopen@0x426a64c`：entry 读取 decoder
   `+0x7f20/+0x28/+0x2c`；835/836 整首重开应为 `0/0/0`；
5. libAMAIN `CSLMng::SndSetVol@0x13066c`：记录 slot 和 w2 int volume；
   `CSound::GetVolNow@0x13646c` entry 读取 `+0x28/+0x08`。正常无 fade 的
   835/836 应为 `50/100`。如需同时保存最终 OpenSL sink，附加在
   `CSLVolume::SetVolumeF+0x54`（module offset `0x1356b0`）读取 w1，预期
   `-602` millibel。

所有 hook 继续以本报告开头的两个 binary hash 为版本锚点，module offset 不符即
fail closed。用户“已经听到 BGM”的确认关闭了 audibility 缺口，但没有同步 code/
slot trace 时仍不能把那一听感瞬间唯一绑定为 835 或 836；上述最小集合就是剩余的
production-mix 归因边界。

## 为什么旧的同线程 join 不够

已静态确认的请求链为：

```text
SoundMng::sndPlayReq@0x425fbdc
  -> SoundMng::wrapSndReq@0x425f09c
  -> CSndMng::SndReq@0x1282a8
  -> CSLMng::SndReq@0x130124
```

`sndPlayReq` 最终固定返回 `-1`，所以返回值不能作为播放 token。并且
`CSLMng::PlayStart@0x12fa9c` 由后续 `CSLMng::Calc@0x12f7c8` 在另一个线程调用，
不能把 thread-local invocation ID 从 `sndPlayReq` 直接传播到 `PlayStart`。

`CSLMng::SndReq` 会在 `[this+0x08, this+0x10)` 的 12-byte row 表中按 request/
resource ID 搜索。匹配行的 `row+8` 给出 slot index，函数再把 exact row pointer
写入 active slot 的 `slot+0x20`。slot stride 是 `0x38`。后续 `CSLMng::Calc`
从同一 `slot+0x20` 读回 row pointer，在 `0x12f864` 调用 `PlayStart(this,
rowPtr, slot)`，然后清除 pending pointer。

因此稳定的物理身份是：

```text
(CSLMng this pointer, slot index, exact row pointer, probe enqueue generation)
```

只有 `PlayStart` 消费同一个 pending row pointer 时才算“实际开始播放”。如果同一
slot 在 Calc 前收到新请求，旧 pending 会被覆盖；probe 必须删除被覆盖的旧映射，
不能留下会误配未来播放的 stale key。

## 运行时精确证明

第一次八 hook 跨线程运行证据：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260715\evidence\natural_hunter_pid3207_cross_thread_csl_execute_20260715_03\hunt_journal.jsonl
SHA-256 42081908D49850F992AD7E58F892555505B7A964A6756C0D9947775DCFDD2E52
```

该次是 1 个 bounded 自然 non-target 回合，credit `37 -> 35`；没有 buffer
overflow、没有 trace drop、没有 Frida error，130 条 sound trace 全部完整。运行时
资源表通过结构校验，共 9951 行。9 个 enqueue 中 8 个被 `PlayStart` 用 exact
`CSLMng + slot + row pointer` 消费；另一个请求在同 slot 被后续请求覆盖，正确地
没有晋升为播放。

| enqueue | `sndPlayReq` call | perform | effective request/resource | final `SSound_Data` ID | slot |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1 | 1 | 43200 | 9002 | 12 |
| 3 | 3 | 3 | 303 | 60 | 2 |
| 4 | 4 | 39 | 3550 | 8573 | 53 |
| 5 | 5 | 43 | 304 | 61 | 2 |
| 6 | 6 | 45 | 3552 | 8575 | 53 |
| 7 | 7 | 47 | 15360 | 856 | 18 |
| 8 | 8 | 48 | 304 | 61 | 2 |
| 9 | 9 | 49 | 304 | 61 | 2 |

第一行还直接证明上游 original resource `301` 可以在进入 CSL 表前 remap 为
effective request/resource `43200`，最后再成为 `SSound_Data` ID `9002`。因此禁止
“按 ac 后缀数字找 CRI index”之外，还要禁止把原始 request、effective resource、
final ID 和 OGG chunk 互相替代。

第一次运行后 probe 又加入了 slot overwrite stale-key 清理。当前源码的只读
provenance 检查点为：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260715\evidence\audible_bgm_pid3207_cross_thread_csl_preflight_readonly_20260715_04\hunt_journal.jsonl
SHA-256 0368D91A6C786E64EFB72F95CBB154240ED7E8096013FC25C1CE45FB19DF0143

sound_logic_chain_probe.js exact injected UTF-8 SHA-256
E2BFBC267227D331A958F34A83518399D8726C46B0C7DCCD01F1431FD4C83CF0

natural_sp_story_hunt.py SHA-256
072C1840AEAB04D588324C1E587FD02A4FAC9F876F8D5E6A37AE6CEB96134405
```

该最后一项是 `execute=false` 的当前源码检查点，不是第二次跨线程播放证明；不能
把它与上一份真实自然回合混写。

后续 ARM64 Gadget 再注入 summary SHA-256 为
`44F1AB99BCD728C34AAD4A4838D97D444CE9FE27EC9B6B959E53E5F978C67534`；当前源码的
新零输入 preflight journal SHA-256 为
`E7B4FF3BC2DBE30702A74D48BA2BA5E6A6459A0F9345F5F668388B3D7CCFA8E6`。在此基础上
又执行两批各五次有界自然 hunt：十次均为 non-target，0 overflow、未伪报 target，
最终普通 credit=19。两个 journal SHA-256 分别为：

```text
6DA701E60A8CD3D5BAB25925C3DFAACC854FA3D6E139E1DB032D5855E7F2ECDE
26902C0927129A1E0A7C4BBAD12F857768EA23FE56D8217A14BF41A6DA78436F
```

这十次没有合法 ac7114/15/16 target，也没有把某次目标入口与 835/836 绑定；它们只
证明新 probe 在自然运行中的完整性，不能降低 target BGM 合同的门禁。

## 与用户听检的合并结论

用户确认 PID3125 的五局自然批次中确实听到了 BGM；同批 active snapshots 捕获
过 volume=50、loop=1 的 835 和 836。现在静态业务语义已经证明两者都是
`BGM_DIR` 代码，因此“它们是否属于 BGM”的缺口已经关闭。

仍未关闭的是**人的听感时刻与单一代码的唯一绑定**：五局结束后的零输入确认晚了
约 14 分 35 秒，不能只凭那份后续空快照宣称人听到的一定是 835 或一定是 836。
现阶段可以安全写入总报告的是：

- 该五局批次有人类证实的可听 BGM；
- 835/836 均为游戏业务层明确请求的 BGM_DIR；
- 同批二者均以非零音量进入 active transport；
- 如需给单一回合或单一场景写 `with_bgm` manifest，仍应在同一次目标事件中捕获
  exact request、source offset/loop phase、volume/transitions 和最终 PlayStart；
- 这项证据不能自动证明 ac7114/ac7115/ac7116 的目标 SP Story 在进入时继承哪一首
  BGM，也不能授权猜测循环相位或 ducking。

## 对生产链的直接约束

1. 运行时记录必须保留 `perform_invocation_id`、`play_request_call_id` 和
   `causal_csl_enqueue_id`，并把跨线程物理 token 作为最终播放门禁。
2. `with_bgm` 层必须保存业务 sound code、request/resource/final ID、原始 OGG hash、
   start/end、source offset、loop points/phase、原生 volume 和 transitions。
3. `no_bgm` 只删除经业务语义证明的 BGM 层；voice/SE 与画面时间轴必须逐字节或逐包
   与 `with_bgm` 对齐。
4. 835/836 已可作为 BGM 正样本用于完善通用静态/动态分类器，但不能把“非 Sound
   Pack 表 + loop=1”泛化为 BGM 判据。
5. 当前 exact cross-thread join 已证明底层调度机制可通用于普通自然声音请求；上游
   玩法如何选择 BGM_DIR 代码、何时切换、如何 duck/fade，仍须分别恢复业务状态字段。

ac7114/15/16 目标路线的上游 `kind/no` writer、提交和清零链已继续收窄，见
`2026-07-15-target-sp-story-bgm-state-upstream.md`。该报告证明 SP Story 自身不发 BGM
request，并明确禁止把 DirInfo 190/191/192 混同为 Direction no；它没有把静态选择
规则冒充目标同 run 的曲目和 phase 证据。
