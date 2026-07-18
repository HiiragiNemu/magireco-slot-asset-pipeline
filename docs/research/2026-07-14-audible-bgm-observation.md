# 2026-07-14 可听 BGM 与运行时 sound ID 对齐

本记录补充一个与 Sound Pack 门控并存、不能混为一谈的事实：用户在 PID3125
自然 normal-play 批次后明确报告“BGM 成功被聆听到”。这是有效的人类听检证据，
但不是仅凭听感给曲目命名的授权。下面只记录同批运行时可以机械核验的事实。

## 证据批次

```text
D:\magia\MyProducts\casino\runtime_recovery_20260714\evidence\natural_hunter_pid3125_bgm_contract_execute_20260714_01\hunt_journal.jsonl
SHA-256 9EB94AF985F8E35BDF2A03696442A39AD5E1F3350C1562E41C20F83199327CCC
```

该批次完成 5 个 bounded 自然回合，全部是 non-target；不能用来晋升
ac7114/ac7115/ac7116。没有 buffer overflow，也没有伪造 entitlement。

约 14 分 35 秒后停止游戏输入并做 8 秒零输入快照（五局 journal 最后一行到该
快照第一行相隔 875.122 秒，并非“立即”）：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260714\evidence\audible_bgm_pid3125_readonly_confirm_20260714_01\hunt_journal.jsonl
SHA-256 C7B52B0CBE83AAC5713E8ECFA72FB660B7230EAA33ECB4619ADE330F0FED8CD8
```

该快照开始和结束时 active vector 都为空，说明它只能证明确认后没有遗留 transport，
不能反推听检时的曲目。真正的同批运行时候选来自五局 journal 自带的 pre/post
active snapshots：

| 回合边界 | sound ID | Sound Pack 表 | runtime volume | time | loop |
| --- | ---: | --- | ---: | ---: | ---: |
| attempt 1 post / attempt 2 pre | 800 | 是 | 0 | 2.848 / 2.944 s | 1 |
| attempt 3 post / attempt 4 pre | 835 | 否 | 50 | 2.965 / 3.061 s | 1 |
| attempt 4 post / attempt 5 pre | 836 | 否 | 50 | 2.986 / 3.104 s | 1 |

ID800 同批门控前整数音量是 50，但 entitlement=0 后 runtime volume=0，因此可以
排除为用户在这五局批次中实际听到的声音贡献者。ID835 和 ID836 不在 222-ID
Sound Pack 表内，实际 runtime volume 都是 50。对应原始资源为：

| ID | source | duration | format | SHA-256 |
| ---: | --- | ---: | --- | --- |
| 835 | `snd_00835_bank01_ogg_00305.ogg` | 13.090896 s | Vorbis 48 kHz stereo | `7F399D88E10387983C2C60785AB83ED7812275B280459A65D31C5322A50C8416` |
| 836 | `snd_00836_bank01_ogg_00306.ogg` | 10.991771 s | Vorbis 48 kHz stereo | `5C57130F5E9A9DE5416458AEDFFB91EB4E2CA5203323B7EE6CC88DBCDDC9F8E4` |

## 结论边界

- 用户确认的是上述**五局批次中确实听到了 BGM**。后续静态逆向已经证明 ID835/836
  都由 `C_ObjNml::fnSndRequest_BGM_DIR()` 直接生成，因此二者的 BGM 业务语义不再是
  猜测；但现有快照仍没有把人的听感时间点唯一绑定到其中一个 ID，不能声称已经唯一
  识别当时听到的是 835 还是 836。
- 当前实例未解锁 Sound Pack，不等于游戏全程无可听 BGM；这次用户听检和运行时
  非零循环 transport 已直接推翻这种错误简化。
- ID835/836 是业务层已证明的 `BGM_DIR` 曲目；这个结论来自原生调用链，而不是
  channel、loop、时长或听感。若要把单一 ID 写入单一回合/场景的 production
  manifest，仍须更窄的同步运行时绑定。
- `with_bgm` 母版必须同时容纳普通可听 BGM 与 Sound Pack 门控曲目；不能只恢复
  222-ID 表，也不能把未授权后的零音量当作原生 no-BGM 设计。
- `no_bgm` 母版应从同一个已验证调度合同中去除所有 BGM 层，同时保持完全相同的
  voice/SE、画面和时间轴；不能从当前实例的偶然静音结果反向拼凑。

## 2026-07-15 当前 PID3207 只读重连检查

MuMu 再次重启后，当前只读探针连接到 PID3207；旧 PID3125 只保留为 dated
evidence。零输入、`execute=false` journal 为：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260715\evidence\audible_bgm_pid3207_current_probe_readonly_20260715_01\hunt_journal.jsonl
SHA-256 68ECC94DF1C3B08C5CD51EAC72636FECBDA0E2CCCF67A9A983C15D34F3585A6D
```

该次 ready payload 验证了版本匹配的 222-ID Sound Pack 表，13 个首/尾/中间 key
check 全部匹配；初始 CSL active snapshot 可用且 `active_rows=[]`。这是重连与探针
provenance 的当前检查点，不是对五局听检曲目的再次捕获，也不能把“当前为空”反推为
五局期间没有 BGM。

## 2026-07-15 加固的 PID3125 快照审计

旧 PID3125 的四份 snapshot journal 已通过失败关闭的版本/表/访问器/provenance
校验重新汇总：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260715\evidence\runtime_sound_pack_snapshot_join_pid3125_hardened_20260715_01

runtime_sound_pack_audit.json
SHA-256 7BD36419637B711A5C4CA051C35C289274673F944E93E6264686B2832B04D295

runtime_sound_pack_rows.csv
SHA-256 3F28CDB1131A08A5EF19E6773A50FCEA9C61AC336099F733C8424F4C5D597094

runtime_sound_pack_pre_gate_volume_rows.csv
SHA-256 7C01DC8CC2E14C5ABAFD1E8A5716C235D3AEB503BEEDB4C3232879EC76FBE992
```

汇总为 32 条 runtime active row，其中 4 条属于 Sound Pack gate（唯一 ID
800/801/821），4/4 runtime volume=0；在 addon index 6 active/saved 都为 0 时有
4 条 corroborating row、0 条 conflict、0 个无效 snapshot。该 snapshot-only 汇总
没有可晋升的 pre-gate event（相关计数均为 0），所以它只加固 entitlement mute
状态证据，不提供 authorized volume，也不唯一识别用户听到的 BGM。

## 2026-07-15 同步调用链预检

在继续消耗剩余游戏 credit 前，sound probe 已加入两个只在真实同步嵌套期间传播的
join key：`perform_invocation_id` 与 `play_request_call_id`。它们可机械连接同一次
`performRequest -> SoundMng::sndPlayReq -> CSLMng::SndReq`；`CSLMng::PlayStart`
实际由另一个 Calc 线程稍后调用，不能继续传播 thread-local ID。相同时间戳或相同
sound ID 仍然只算相关性，不自动升级为因果关系。

当前 PID3207 的 12 秒零输入预检为：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260715\evidence\audible_bgm_pid3207_sync_trace_preflight_readonly_20260715_02\hunt_journal.jsonl
SHA-256 0C6B9BD366505B800DA40948CB38644A2FA4DF969261DCD99EB270EF15E87967
```

结果是 `execute=false`、2 条 journal row、PID3207；7 个主要 sound hook、8 个
active-sound accessor、`CSLMng::Calc` 一次性快照入口及 13 个 gate key check
全部通过版本校验，初始 `active_rows=[]`。加载的 probe/hunter 源码 SHA-256 分别为
`E88EB8D51FD20A85DA959FB259DD1E5557DE2BA6A51BCBDF49A4DE4C29831BBD` 与
`10E9110809A35F1D0F429337D0E15B5E788E0ADC6FC4711D26EEA62DC94B5A09`；
三份 probe 的 hash 都在读入并传给 `create_script` 前由同一字节串计算，不再事后
重读可能已变化的路径。
这证明下一次自然回合在输入前具备所需捕获能力；它本身不识别 ID835/836，也不消耗
credit。

## 2026-07-15 BGM_DIR 静态证明和跨线程 CSL join

`libGameProc.so` 的 `C_ObjNml::fnSndRequest_BGM_DIR@0x43a86b0` 已直接证明：
当 `[this+0xca] == 0x2f` 时，状态 `[this+0x11a]` 为 `1..24` 选择 sound code
`835`，大于等于 `25` 选择 `836`，变化时调用
`C_CtrlSndLib::fnReqSndSoundCode(code, 1)`。因此原记录中“尚未证明二者在业务层
属于 BGM”的限制已经关闭。

底层线程边界也已静态和动态闭合：`CSLMng::SndReq@0x130124` 把匹配的 12-byte
资源表 row pointer 写到 `slot+0x20`，`CSLMng::Calc@0x12f7c8` 在另一线程取回同一
pointer 后调用 `PlayStart@0x12fa9c`。probe 以
`(CSLMng*, slot, row pointer, enqueue generation)` 做物理 token，并在同 slot
被覆盖时删除旧 pending key。

首次八 hook 的真实自然回合：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260715\evidence\natural_hunter_pid3207_cross_thread_csl_execute_20260715_03\hunt_journal.jsonl
SHA-256 42081908D49850F992AD7E58F892555505B7A964A6756C0D9947775DCFDD2E52
```

该次 130 条 sound trace 完整、0 drop、0 Frida error；9 个 enqueue 中 8 个用 exact
pending row pointer 与 PlayStart 对齐，另 1 个在同 slot 被覆盖而正确不晋升。当前
加入 stale-key 清理后的只读源码检查点为：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260715\evidence\audible_bgm_pid3207_cross_thread_csl_preflight_readonly_20260715_04\hunt_journal.jsonl
SHA-256 0368D91A6C786E64EFB72F95CBB154240ED7E8096013FC25C1CE45FB19DF0143
```

完整地址、编号层级、OGG hash 和结论边界见
`2026-07-15-bgm-dir-and-csl-cross-thread-identity.md`。这项突破证明通用声音 transport
可在外部非黑盒化，但仍没有把 PID3125 人工听到的时刻唯一归给 835 或 836，也没有
自动证明目标 ac7114/ac7115/ac7116 进入时继承的 BGM、loop phase 或 ducking。
