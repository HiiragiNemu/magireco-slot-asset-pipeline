# 2026-07-14 Sound Pack 门控前音量与双音频母版

本报告记录一次会改变最终交付规格的机制闭环。当前 MuMu 实例没有任何 addon
entitlement，Sound Pack 索引 6 为 0；这只能解释当前实例为何听不到受门控音乐，
**不能取消带 BGM 成片目标**。最终发布矩阵固定为：

| 音频母版 | 无字幕 | 日文字幕 | 中文字幕 |
| --- | --- | --- | --- |
| `with_bgm`：BGM + 原生语音/SE | required | required | required |
| `no_bgm`：不含 BGM，保留同源语音/SE | required | required | required |

两条音频母版的语音和 SE 必须同源、同时间轴、同 hash。`with_bgm` 还必须逐层记录
BGM source hash、request/start、循环相位、原生音量单位、ducking/volume transition
以及官方运行时或版本匹配静态证据。缺一项就 fail closed，不能把“当前未授权所以
静音”误写成“游戏没有 BGM”，也不能猜配一首曲子。

## 1. 原生整数音量链

版本匹配 `libGameProc.so` SHA-256：

```text
5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF
```

`SoundMng::changeVolume(int,int)@0x425ee68` 的 ARM64 逻辑可还原为：

```text
volume_class = sound_id_to_class[sound_id]        # 0..2
class_volume = SoundMng[volume_class]
indexed_volume = SoundMng[0x82c + volume_index*2]
stage_volume = floor(class_volume * indexed_volume / 100)

if SoundPack active index 6 == 0 and sound_id in 222-ID gate table:
    stage_volume = 0

master_volume = SoundMng[0x8ac]
final_volume = floor(stage_volume * master_volume / 100)
```

门禁前值不是通过篡改 entitlement 得到的。新版只读探针在函数入口读取原生参数和
已命名字段，按同一整数链计算 counterfactual authorized volume；不替换返回值、
不写内存、不调用 native 函数。实现与测试：

```text
tools/frida_runtime_probe/sound_logic_chain_probe.js
tools/frida_runtime_probe/natural_sp_story_hunt.py
tools/frida_runtime_probe/audit_runtime_sound_pack_state.py
test_sound_logic_chain_probe.py
test_natural_sp_story_hunt.py
test_audit_runtime_sound_pack_state.py
```

探针只观察 222 项版本匹配表成员。直接声音请求调用始终保留；`volumeControl` 的
重复不变状态会被抑制，只记录第一次和真正的 volume/ducking transition。host 侧
再把连续同状态聚合为 observation count，避免逐帧日志浪费。

## 2. PID3125 运行时结果

零输入 smoke 精确匹配：

```text
symbol               _ZN8SoundMng12changeVolumeEii
actual/expected      0x425ee68 / 0x425ee68
gate table           222 entries, strictly increasing and unique
key checks           67,171,778,786,863,9070,9071,41030,41031,41032 all match
gameplay input       0
journal SHA-256      2B132B50606FFB01C20AD507C1C836BF2AB2D68DC79F1EDEA11AA9E2636537FF
```

随后三局是自然 normal-play non-target；没有合法 ac7114/15/16 target，不能用于目标
场景晋升。其中真实 `wrapSndReq` 调用了受门控 `ID826`：

```text
sound ID                         826
sound asset                      snd_00826_bank01_ogg_00296.ogg
asset duration / format          33.000042 s / Vorbis 48000 Hz stereo
asset SHA-256                    48F0455580E119CB92A86D6850356CBA68DA27BE62E69C107888C1E579DF1BEB
volume index                     1
volume class                     0
class / indexed / master         50 / 100 / 100
pre-gate stage/final volume      50 / 50
Sound Pack active               0
post-gate CSL runtime volume     0
direct request return offset     0x425f160
volumeControl return offset      0x425f918
raw three-attempt journal SHA    388950E6FA2A9AAE67E3944EF791F3A061BFDCA10B9747FC9BA3C2301A66344D
```

因此“当前听不到音乐”与“已解锁路径本应以原生音量 50 播放 ID826”可在同一版本的
真实调用链中同时成立。这是外部复刻 BGM 混音参数的直接机制证据，不是听感分类。

跨五个 PID3125 自然 journal 的 compact join：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260714\evidence\runtime_sound_pack_join_pid3125_20260714_03
```

结果：48 个 active rows；Sound Pack 表成员 7 rows、4 个唯一 ID
`800/801/821/826`；7/7 都是 proven playing transport 且 runtime volume 0；0 个
非零矛盾。门控前 660 次旧探针 observation 被压缩为 5 个 compact state groups，
全部可重建；这些旧记录缺少 emission reason，不能冒充 5 次真实 transition。当前
只覆盖 ID826，authorized final volume 唯一值为 50。

```text
runtime_sound_pack_audit.json
  SHA-256 637C90791CB9BF65DC0FE72D0EF4B23288D80869A166AEFEB1C6F0D34938B2DC
runtime_sound_pack_rows.csv
  SHA-256 882138D9FDEC806B189891F20CC6C25D03BF8510C608A4C1F23ED440D6C34E68
runtime_sound_pack_pre_gate_volume_rows.csv
  SHA-256 28D7048CA6F8CCB77C0E8786E704BA203D126336309C18F33FC0529A88B0FE64
```

## 3. 对最终 BGM 复刻的边界

已解决：

- Sound Pack 静音不是普通 BGM/SE/Voice 设置或 Android 系统 mute；
- 版本匹配的 222-ID 门禁、实际 active index、运行时 zero-volume transport 已连接；
- 即使 entitlement 为 0，也能只读恢复门控前原生整数音量；
- ID826 已获得 request call、门控前 50、门控后 0、OGG hash 的完整链。

仍需在**同一次目标事件自然运行**中解决：

- ac7114/ac7115/ac7116 入口前后实际继承哪一个 Sound Pack ID；
- 目标开始时的 `sound_time_seconds`/循环相位，而不是默认从 OGG 0 秒猜起；
- 目标内的音量/ducking transition；
- 目标结束或下一段之间是延续、停止、换曲还是重新起播；
- BGM+语音/SE 母版和 no-BGM 母版的 packet/timeline/hash QA。

当前实例无需伪造购买状态即可继续获得上述 pre-gate 调度证据；禁止写 entitlement。
如果将来用户合法购买或切换到合法已购账号，可做只读 A/B 复核，但它不是继续静态/
pre-gate 逆向的前置条件。

同日后续自然批次中，用户确认实际听到了 BGM；运行时同时出现不受 Sound Pack 表
门控、volume=50、loop=1 的 ID835/836。它证明“未解锁 Sound Pack”绝不等于“停止
带 BGM 成品”，但精确曲目语义仍需调用链绑定。见
`2026-07-14-audible-bgm-observation.md`。
