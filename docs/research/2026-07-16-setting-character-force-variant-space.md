# 2026-07-16 台设定、角色与强制役的真实变体空间

## 结论摘要

本报告回答一个有界问题：台设定 `1..6/?`、标题页五角色、
`g_CustomChara/g_CustomVoice` 和强制役 `0..19` 到底构成多少个需要归档的媒体变体，
以及它们是否能加速 `ac7114_001` / `ac7115_001` / `ac7116_001` 的自然 BGM
门禁取证。

结论如下：

1. 官方有效台设定严格为 `0..5` 六值；UI 的 `?` 是“随机选择模式”，进入游戏前会
   解析为六值之一，不是第七种台设定。
2. 标题页官方角色严格为 `0..4` 五值。正常 UI 把 `g_CustomVoice` 固定为 `0`，所以
   官方空间是五个角色 profile，不是 `5 x 5` 的角色/voice 笛卡尔积。
3. 强制役 `0..19` 是小役/bonus trigger 域，不是 SP Story stage kind、selector、
   DirInfo kind 或 `ac` 文件名后缀。有效 post-clear 扫描没有一个进入目标 SP Story。
4. 台设定影响普通 Story kind/character 候选彩票；目标使用的
   `fnLot_OT_AT_SpStryKnd` 不读台设定，只按 `SdGmData+0x592` 选择五张 SP Story
   权重表。
5. 因而不得为每个事件盲目生成 `7 x 5 x 20 = 700` 份组合。只有同一 canonical
   event code 的视频源、voice request 或字幕 cue 签名确实变化时，才建立独立 edition。
6. 解锁固定设定或强制役可以方便普通路线诊断，但不会关闭 ac7114/15/16 尚缺的
   natural outer-flow BGM/phase/fade/duck/stop 证据门。

本轮是只读静态分析与既有运行时 evidence 汇总，没有修改购买状态、游戏状态或媒体。

## 二进制与证据基线

```text
libGameProc.so
path D:\magia\MyProducts\casino\magireco_corrected_research_20260612\native_analysis\libGameProc.so
size 79683640 bytes
SHA-256 5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF
```

主要耐久输出：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\static_story_lottery_tables_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\dirinfo_event_table_decode_v3_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\sp_story_event_code_extract_routes_v2_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260713\static_sp_story_kind_lottery_20260713
```

有效强制役扫描 evidence：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\force_kind_scan_smoke_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\force_kind_scan_smoke_kind2_v3_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\force_kind_scan_3_7_9_19_v2_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\force_index8_postclear_probe_20260703
```

下文地址均是该 ARM64 `libGameProc.so` 的静态 VMA。ASLR 运行时地址必须由模块基址
加相对偏移求得，并先验证架构和 binary hash。

## 台设定：六个有效值加一种随机选择模式

### 标题页状态与购买门

`CScnTitleSmu::CScnTitleSmu@0x4244e80` 在 `0x4244f00..0x4244f28` 从
`0x1440b88` 读取八字节常量：

```text
06 00 00 00 00 00 00 00
```

并写到 scene `+0x18c`。因此初始 UI 状态为：

| scene offset | 初始值 | 含义 |
| ---: | ---: | --- |
| `+0x18c` | 6 | 台设定选择为 `?` |
| `+0x190` | 0 | 角色 hover/当前选择为第一人 |

`CScnTitleSmu::Calc@0x4245a7c` 的按钮域为：

| UI 按钮 | 内部值 | 含义 | Settings Change 门控 |
| ---: | ---: | --- | --- |
| 0..5 | 0..5 | 台设定 1..6 | 是 |
| 6 | 6 | `?` 随机模式 | 否 |
| 7..11 | 0..4 | 五角色 | 否 |

确认固定设定的购买检查在 `0x4245ddc..0x4245df4`。scene `+0x330` 指向
`CplayData+0x14b6c`，Settings Change active 位相对该指针为 `+0x90`，即绝对
`CplayData+0x14bfc`。按钮 6 不经过这项确认门。

新游戏路径在 `0x4245bb0..0x4245bc4` 把 scene `+0x18c` 写到：

```text
CplayData+0x14bb8
= (CplayData+0x14b6c)+0x4c
```

### 随机值的官方解析

`gat_CallBack@0x4247574` 是选择值进入机台前的实际 resolver：

```text
0x4247618..0x4247630
CplayData+0x14bb8 -> CplayData+0x14470

if selected == 6:
    effective = getRandRange(6)
    CplayData+0x14470 = effective
```

`getRandRange@0x425ec30` 的核心使用 AArch64 `udiv` 加 `msub` 计算余数，因此这里的
精确语义是 `random32 % 6`，输出严格在 `0..5`。所以：

- `6` 只应保存在“选择方式”provenance 中；
- 游戏玩法的有效 setting dimension 只有六个值；
- 同一 random run 若观察到 resolver 结果，还应保存最终 `setting_effective`；
- 不得把 `?` 渲染为第七个媒体 edition。

### 台设定影响的普通 Story 彩票

`fnLot_OT_AT_StryKnd@0x445e220` 与
`fnLot_OT_AT_StryChara@0x445e4e0` 都读取 `SdGmData+0x22` 的实际台设定，并检查
其小于 6。

| 函数 | runtime descriptor | 布局 | selector/request | 结果写入 |
| --- | ---: | --- | ---: | --- |
| `fnLot_OT_AT_StryKnd` | `0x4b28d40` | 6 x 16 bytes | 62 | `SdGmData+0x1f72..0x1f80` |
| `fnLot_OT_AT_StryChara` | `0x4b28da0` | 2 banks x 6 x 16 bytes | 64 | `SdGmData+0x1f94..0x1f9c` |

第二个函数先按另一条件选择相距 `0x60` 的 descriptor bank，再以
`setting * 0x10` 选该 bank 内描述符。两段 descriptor 位于 `.bss`/runtime relocation
区域；文件中的零值不代表权重为零。

彩票结果再选择以下静态候选顺序表：

| 表 | VMA/file offset | 形状 | 说明 |
| --- | ---: | ---: | --- |
| `lot_ot_at_stryknd_table` | `0x2f44406` | 19 records x 8 u16 | 普通故事 kind 候选顺序 |
| `lot_ot_at_strychara_table` | `0x2f44536` | 23 records x 5 u16 | 普通故事 character 候选顺序 |

这两张表是候选排列，不是六张台设定表，也不是标题页五角色的 identity 表。
台设定改变候选/概率路径，但不创造新的 canonical event inventory。

### 目标 SP Story 彩票不读台设定

目标 ac7114/15/16 使用另一函数：

```text
fnLot_OT_AT_SpStryKnd@0x445e698
descriptor array @0x4b28e60
result -> SdGmData+0x1f82
```

它不读取 `SdGmData+0x22`。它只按 `SdGmData+0x592` 选择五张权重表：

| `+0x592` | 表 | SP Story kind 权重 |
| ---: | ---: | --- |
| 0..1 | 00 | 11: 33.334%; 12: 33.334%; 14: 33.331% |
| 2 | 01 | 11: 33.334%; 12: 33.334%; 14: 33.331% |
| 3 | 02 | 11: 3.125%; 12: 3.125%; 13: 90.625%; 14: 3.125% |
| 4 | 03 | 9: 85.938%; 11: 1.563%; 12: 1.563%; 13: 9.375%; 14: 1.563% |
| >4 | 04 | 9: 93.750%; 11/12/13/14: 各 1.563% |

每张表的整数权重和为 32768。表权重只能估计自然搜索成本；真正进入函数还需要外围
SP Story gates。固定台设定 1..6 不能直接打开或偏置这条目标 stage-kind 彩票。

## 角色：五个官方 profile，不是二十五个组合

### UI 到全局变量

在 `CScnTitleSmu::Calc`：

- `0x4245c80..0x4245c98` 把按钮 `7..11` 映射为角色 `0..4`，写 scene `+0x190`
  并更新 UI；
- `0x4245cb8..0x4245ccc` 把确认后的角色写 scene `+0x198`；
- `checkCharBtn@0x424619c` 使用相同五值边界；
- 以上路径都不读 Settings Change entitlement。

用户截图对应的顺序为：

| UI/internal index | 角色 |
| ---: | --- |
| 0 | 环伊吕波 |
| 1 | 七海八千代 |
| 2 | 由比鹤乃 |
| 3 | 深月菲莉希娅 |
| 4 | 二叶纱奈 |

相关全局变量：

```text
g_CustomChara @0x4c202c4
g_CustomVoice @0x4c202c8
```

constructor 在 `0x4245564` 以一个 `str xzr,[scene,#0x198]` 同时把提交角色和
custom voice 清为 0。正常新游戏路径 `0x4245ef8..0x4245f1c` 把 scene `+0x198`
写入 `g_CustomChara`，把 scene `+0x19c` 写入 `g_CustomVoice`；正常角色选择只写
`+0x198`，不写 `+0x19c`。另一个确认回调 `0x4246660..0x424667c` 同样写选中角色，
并显式把 `g_CustomVoice` 写成 0。

对两个 GOT slot 的全量交叉引用只发现上述标题写入点和 `CSlotBody::newSlot` 读取点。
因此 `g_CustomVoice=1..4` 虽被下游接受，却没有正常 UI 可达写入路径，不能枚举成官方
角色版本。

### `CSlotBody::newSlot` 的下游映射

`CSlotBody::newSlot@0x424bd64`：

- `0x424be5c..0x424be7c` 检查 `g_CustomChara <= 4` 并写 `SGmData+0x2a8`；
- `0x424be80..0x424c12c` 检查 `g_CustomVoice <= 4` 并写 `SGmData+0x2ac`。

角色 index 随后经过两张五项表：

| 表 VMA | 内容 | 用途 |
| ---: | --- | --- |
| `0x14457be` | `[0, 2, 4, 6, 5]` | 写 `SdGmData+0x1164` 的主角色映射 |
| `0x14457c8` | `[0, 1, 2, 4, 3]` | 传给 `fnUniMemoRx_SelectChara@0x448c25c` |

`fnUniMemoRx_SelectChara` 还使用 `0x416dcc2` 的查找表；其前 25 项为：

```text
[0, 2, 4, 5, 6, 7, 8, 9, 10, 12, 14, 16, 18, 20, 22,
 24, 25, 26, 27, 28, 29, 30, 31, 32, 33]
```

对正常 UI 的第二张表输入，主 identity 最终仍归并为 `[0,2,4,6,5]`；新初始化状态下
`+0x122c` 对伊吕波为 0，对其余四人为 1。这里证明角色选择是实际 presentation/game
state 维度，但没有证明每个 canonical event 都产生五份不同媒体。

函数名中的普通彩票 `StryChara` 与标题页 `g_CustomChara` 也不是同一字段：前者读台设定
并选择普通故事候选，后者选择玩家 profile。不得因名称相似把两者连接起来。

## 强制役 0..19：trigger provenance，不是 SP Story selector

### 原生调用链

```text
CScnSlot::addonForceSelectExecute@0x4235af0
    -> UI selection clipped to 0..19
CScnSlot::onStartInit@0x423a11c
    -> CSlotBody::setForceMainFlag@0x4253d04
    -> body+0x520
```

相邻内部字段为：

```text
setForceSubFlag   -> body+0x524
setForceFlagPalam -> body+0x528
```

这是强制小役/bonus flag。它不是事件编号；flag 被消费后仍要经过普通彩票、状态门和
DirInfo/EventInfo 调度。

### 有效 post-clear 扫描的观测范围

下表只压缩列出每个 kind 的已解析事件 family；`ac9071`/`ac9920` 等公共路线也保留，
避免把同次 capture 中的非目标公共请求误判为强制役的唯一 identity。

| force kind | 已观测事件 family | SP Story 目标 |
| ---: | --- | --- |
| 0 | flag 已消费；普通/非目标路线 | 无 |
| 1 | ac0101, ac0907, ac9071, ac9920 | 无 |
| 2 | ac0902, ac0907, ac9071, ac9920 | 无 |
| 3 | ac0910, ac9071, ac9920 | 无 |
| 4 | ac0909, ac0910, ac9071, ac9920 | 无 |
| 5 | ac0904_055, ac9071, ac9920 | 无 |
| 6 | ac0905, ac0912, ac9071, ac9920 | 无 |
| 7 | ac0911, ac9071, ac9920 | 无 |
| 8 | 旧 run 为 ac0922_001；后续校准为 ac0101/ac0102/ac9071/ac9920 | 无 |
| 9 | ac0901, ac9071, ac9920 | 无 |
| 10 | ac0902_277, ac0906_001, ac9071, ac9920 | 无 |
| 11 | ac0103, ac0902_126, ac9071, ac9920 | 无 |
| 12 | ac0907, ac9071, ac9920 | 无 |
| 13 | ac0907, ac0915, ac9071, ac9920 | 无 |
| 14 | ac0103, ac0912, ac9071, ac9920 | 无 |
| 15 | ac0905, ac0917, ac9071, ac9920 | 无 |
| 16 | ac0910, ac0914, ac9071, ac9920 | 无 |
| 17 | ac0102, ac0907, ac9071, ac9920 | 无 |
| 18 | ac0904, ac0906_005, ac9071, ac9920 | 无 |
| 19 | ac0101, ac0904, ac9071, ac9920 | 无 |

所有有效 `0..19` post-clear 样本的目标判断均为 false，且
`sp_story_state_count=0`。kind 8 在不同 run 的具体普通路线不稳定，说明 force kind
定义的是上游 trigger，不应硬编码成某一个 canonical event。

### 目标事件属于独立的 `(stage kind, selector)` 域

四条已解析目标 event code：

| event | official 64-bit event code |
| --- | --- |
| `ac7114_001` | `0x4f71466b3d723041` |
| `ac7115_001` | `0x5773382374447854` |
| `ac7115_013` | `0x4c792a5a74447854` |
| `ac7116_001` | `0x2476304366614152` |

`C_ObjStageAT_SP_Story::fnSetEvCdBase` 静态 route 表把它们解析为：

| event | stage kind (`this+0x318`) | selector (`this+0x34a`) |
| --- | ---: | --- |
| `ac7114_001` | 11 | 1, 2 |
| `ac7115_001` | 12 | 1, 2, 3, 4 |
| `ac7115_013` | 12 | 13, 14 |
| `ac7116_001` | 13 | 1, 2 |

运行时复制链为：

```text
MSTCOMCBK()+0x2376 -> C_AnmBase+0x318
SdGmData+0x788 -> MSTCOMCBK()+0x2378
                 -> C_AnmBase+0x31a
                 -> C_ObjStageAT_SP_Story+0x34a
```

DirInfoTable 中 ac7114/ac7115/ac7116 的 record kind 又分别是 `190/191/192`。直接把
`190` 传给 `fnSetForceFlag` 的既有诊断没有得到目标，值被拒绝/归一为非目标状态。

因此以下五类数字必须严格分开：

1. `ac` 文件名后缀；
2. DirInfo record kind `190/191/192`；
3. force kind `0..19`；
4. SP Story stage kind `11/12/13`；
5. SP Story selector `1..14` 中的已解析子集。

按 `ac7116` 的 `16`、DirInfo 的 `192` 或 force index 直接寻找 CRI/事件索引，都会制造
错误映射。

## 全量静态 inventory 与数量基线

`decode_dirinfo_event_tables.py` 的 v3 耐久输出给出：

| 项目 | 地址/大小 | 数量 |
| --- | --- | ---: |
| `DirInfoTable` | `0x44c0210`, 4640 bytes | 290 有效 entries |
| `EventInfo` | `0x44c1430`, 233568 bytes | 9732 records |
| unique reachable event codes | — | 9731 |
| DirInfo route rows | — | 37266 |
| route cells | — | 122028 |
| 当前 manifest 已解析 canonical codes | — | 926 |
| 当前已解析 route rows | — | 3908 |

`invalid_event_index_count=0`，说明该表解码适合作为枚举骨架。数量也直接说明：项目应该
从静态 canonical inventory 出发建立等价类，而不是对 9731 个 event 逐个运行
setting/character/force 的完整组合。

## 归档字段合同

事件 manifest 建议保存以下 provenance；字段“存在”不等于必须生成独立成片：

```json
{
  "setting_selection_mode": "fixed|random",
  "setting_selected_ui": 6,
  "setting_effective": 0,
  "custom_chara_ui": 0,
  "custom_chara_internal": 0,
  "custom_voice": 0,
  "custom_voice_route": "official_title_ui",
  "force_kind": null,
  "force_route": "natural|diagnostic_forced",
  "sp_story_stage_kind": 11,
  "sp_story_selector": 1,
  "dirinfo_kind": 190,
  "canonical_event_code": "0x4f71466b3d723041"
}
```

约束：

- `setting_selected_ui=6` 时仍应保存本次实际解析出的 `setting_effective=0..5`；若未观察
  resolver，则写 null，不能猜。
- `custom_chara_ui=0..4` 映射到 `custom_chara_internal=[0,2,4,6,5]`。
- 正常官方标题路径的 `custom_voice` 为 0；值 1..4 只能标为 debug/unknown route，
  不进入官方 edition 计数。
- `force_kind` 只记录触发 provenance。forced capture 不能证明自然概率、自然外层 BGM
  继承或进入 phase。
- `sp_story_stage_kind`、`sp_story_selector`、`dirinfo_kind` 与 event code 分字段保存，
  禁止用其中一个推导另一个，除非有本版静态 route 表证据。

## 最小通用枚举器建议

建议扩展：

```text
tools/frida_runtime_probe/decode_dirinfo_event_tables.py --variant-summary
```

或新增：

```text
tools/frida_runtime_probe/enumerate_runtime_variant_dimensions.py
```

输入：

1. `libGameProc.so` 及 SHA-256；
2. `dirinfo_event_table_decode_v3_20260703/summary.json`、
   `resolved_scene_catalog.csv`、route CSV；
3. 普通 Story 两张候选表和 SP Story 五张权重表；
4. 五角色 UI/internal 映射常量；
5. force scan summary；
6. resolved event manifest 中的视频源 hash、voice request、字幕 cue。

建议输出 `runtime_variant_dimensions.json` 和 CSV：

```text
setting_selected_ui: 0..6
setting_effective: 0..5
custom_chara_ui: 0..4
custom_chara_internal: 0,2,4,6,5
custom_voice_official: 0
force_kind: trigger provenance only
```

核心分组键：

```text
canonical_signature = (
    event_code,
    ordered_video_source_hashes,
    ordered_voice_request_ids,
    subtitle_cue_hash
)
```

枚举算法：

1. 静态解出全部 canonical event code 和 route rows；
2. 将 setting/character/force 作为可能的上游 provenance 边，不先复制媒体；
3. 对已有 manifest 计算 `canonical_signature`；
4. 只有静态数据表明某个维度会改 event/voice/source，或同一 event 的有界 A/B
   实际产生不同签名时，才把该维度升级为独立 edition；
5. 签名相同的运行记录归并到一个 canonical media item，同时保留所有 provenance；
6. forced 与 natural 始终分组，forced 结果不能批准 natural BGM gate。

这样既避免 700 倍盲跑，也保留了日后证明角色 voice 确实变化时增量扩展的能力。

## 对 ac7114/15/16 与购买状态的直接影响

目前两条最像“付费后能加速目标”的路线均已被机制证据排除：

- Settings Change 只让用户固定 `0..5`；免费的随机模式最终也覆盖同一六值，而且目标
  `fnLot_OT_AT_SpStryKnd` 根本不读 setting 字段。
- Forced Role 0..19 可快速触发一部分普通路线，但有效全扫没有进入目标
  `C_ObjStageAT_SP_Story`，且无法复现自然外层声音状态。

因此购买状态变化最多改善 UI 操作便利和普通事件覆盖率，不会证明以下仍缺项目：

```text
natural target hit
-> exact stage/selector/event acceptance
-> high-level BGM request
-> source hash and native volume
-> loop phase at entry
-> fade / duck / stop
-> final CSL/OpenSL queue
```

剩余高收益路线仍是自然 hunter，优先围绕 SP Story 外围 gates 和
`SdGmData+0x592` 做有界状态记录；自然命中时在同一 run 连接 stage/selector、event code
与 BGM request/phase/volume/fade/duck/stop。该证据闭环后，才能批准 ac7114/15/16 的
`with_bgm` Bilibili 长片母版。

## 解释边界

- 本报告证明的是当前 binary 的维度边界和已知路由，不声称每个普通事件都与角色无关。
- 五角色确实进入游戏状态；在同一 event 的 voice/source A/B 尚未出现前，只记录
  provenance，不预生成五份相同视频。
- 强制役扫描是诊断证据，不是自然出现概率或自然音轨证据。
- 静态 SP 权重表解释概率，不绕过外围 gates，也不代替自然运行时事件接受证据。
- 旧 A: 路径可能因 RAM-disk 断电丢失；本报告只把 D: 耐久输出和仓库记录作为可续接
  基线。
