# 2026-07-15 目标 SP Story 的 BGM_DIR 上游状态链

## 结论

仅凭 `ac7114/ac7115/ac7116`、SP Story stage/selector 或 event code，不能静态指定
835 或 836。静态分析能确定的是全局 Direction 选择策略：

- 当前方向 `kind == 0x2f`；
- 当前方向 `no` 为 `1..24` 时，`BGM_DIR` 选择业务代码 835；
- 当前方向 `no >= 25` 时，`BGM_DIR` 选择业务代码 836。

实际进入目标事件时的 `kind/no` 是可继承的全局状态，有提交、恢复和清零等多条
writer；目标 SP Story 对象自身不设置 BGM。用户已经听到 BGM，证明运行态有可听音乐，
但不能据此区分 835/836、判定是否继承前一场景，或确定入口 loop phase。

静态锚点：

```text
libGameProc.so
size 79683640 bytes
SHA-256 5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF
```

以下地址均为该 ELF 的 module-relative offset；另一版本必须先复核 hash 和符号。

## 全局状态到 BGM_DIR 的因果链

```text
SdGmData+0x13da / +0x13de
  -> C_MstComCbk::fnUpDateGmData
MSTCOMCBK+0xa72 / +0xa76
  -> C_AnmBase::fnDataSetDir_DIR
C_ObjNml+0xca / +0x11a
  -> C_ObjNml::fnSndRequest_BGM_DIR
C_ObjNml+0x800 cached code pointer
  -> C_CtrlSndLib / zgSndReqCode
  -> PlayerImpl / CSL
```

### 提交到对象

`C_MstComCbk::fnUpDateGmData@0x4399a4c`：

- `0x4399a70..0x4399a8c` 从 `SdGmData+0x968` 向 `MSTCOMCBK` 复制
  `0x4908` bytes；
- 因此 `MSTCOMCBK+0xa72/+0xa76` 分别来自
  `SdGmData+0x13da/+0x13de`。

`C_AnmBase::fnSetCmnData@0x4386bc8` 在 `0x4386c54..0x4386c58` 调用
`C_AnmBase::fnDataSetDir_DIR@0x4387f90`。后者：

- `0x4387fc0..0x4387fc8`：`MSTCOMCBK+0xa72 -> C_ObjNml+0xca`；
- `0x4387fd8..0x4387fe0`：`MSTCOMCBK+0xa76 -> C_ObjNml+0x11a`。

`C_ObjNml::fnCtrlSnd@0x43a2188` 在 `0x43a2358..0x43a235c` 调用
`fnSndRequest_BGM_DIR@0x43a86b0`。835/836 的具体选择和 ReqData/CSL 映射见
`2026-07-15-bgm-dir-and-csl-cross-thread-identity.md`。

## 主要上游 writer

`fnKndCalLot_CcDirEnd@0x4445e3c`：

- `0x4445ed4/0x4445edc`：`next kind +0x13dc -> current kind +0x13da`；
- `0x4445ee4/0x4445eec`：`next no +0x13e0 -> current no +0x13de`。

`fnKndCalLot_RlStart@0x444466c`：

- 当状态 `+0x1472 == 1`：
  - `0x4444848..0x4444850`：saved `+0x1474 -> +0x13da`；
  - `0x4444978..0x4444980`：saved `+0x149a -> +0x13de`；
- 当状态 `+0x1472 == 3`：
  - `0x4444ae8` / `0x4444b80` 清零当前 kind/no。

`CScnSlot::onStatLoop@0x423a768`、`fnOther_DirSet_Prize@0x446ba7c`、
`fnOther_DirSet_LockStt`、`fnOtherUpdate` 等还会清零或重写这些字段。因此当前
`kind/no` 不是目标 event code 的静态常量。

## 为什么 190/191/192 不能推成 836

`fnLot_OT_AT_SpStryKnd@0x445e698` 在 `0x445e7bc..0x445e7c0` 把 SP Story kind
写入 `SdGmData+0x1f82`。ac7114/ac7115/ac7116 对应的 DirInfo 表记录号分别为
190/191/192；这些是另一套 SP Story 路由字段，不是 `SdGmData+0x13de` 的 Direction
`no`。把 190/191/192 当成“均大于 25”，进而指定 836，是字段混淆，必须禁止。

目标对象的本地声音入口也没有隐藏 BGM 请求：

- `C_ObjStageAT_SP_Story::fnSndRequest@0x43dc3dc`：直接 `ret`；
- `post@0x43dc3e0`：直接 `ret`；
- `end@0x43dc3e4`：直接 `ret`；
- `pre@0x43dc260` 只处理场景事件字段，没有本地 BGM request。

这支持“目标场景继承外层全局 BGM 状态”，但不证明具体继承哪一首或入口相位。

## 同帧停止、淡出和替换仍须捕获

`fnCtrlSnd` 在同一帧先后调用：

```text
0x43a2298 BGM_DIR_NEXT
0x43a22a8 BGM_FADE
0x43a22b0 BGM_FADE_NEXT
0x43a22b8 BGM_END
0x43a22c0 BGM_STG
0x43a2350 ATST_FADE
0x43a2358 BGM_DIR
```

其中 BGM_DIR_NEXT 使用 `C_ObjNml+0xf2/+0x142`，BGM_FADE_NEXT 使用
`+0x106/+0x156`，BGM_END 检查 `+0xca == 0x26`。所以即使 BGM_DIR 自己的 ReqData
没有 fade/duck，同帧也可能有独立 stop/fade/replacement request。`C_ObjNml+0x800`
只是声音代码指针缓存，reset 时变成空字符串；它不保存 decoder 采样位置或 loop
phase。

## 最小同 run 动态证明

下一次合法自然目标只需要增加下列有界字段，不再回到宽泛黑盒 hook：

1. `fnLot_OT_AT_SpStryKnd@0x445e698` leave：记录 `SdGmData+0x1f82`。
2. 精确 ID24/event 接受点：记录 stage、selector、最终 `ac` event。
3. `fnKndCalLot_CcDirEnd@0x4445e3c` 与 `fnKndCalLot_RlStart@0x444466c`
   entry/leave：记录 `+0x13da/+0x13dc/+0x13de/+0x13e0/+0x1472/+0x1474/+0x149a`。
4. `fnUpDateGmData@0x4399a4c` leave 与 `fnDataSetDir_DIR@0x4387f90` leave：证明
   快照时序以及目标 `C_ObjNml+0xca/+0x11a`。
5. `fnSndRequest_BGM_DIR@0x43a86b0` entry/leave：记录 `+0xca/+0x11a/+0x800`
   旧/新值；同时在 `zgSndReqCode@0x4273058` 捕获同帧所有请求，避免漏掉前置
   fade/stop。
6. `PlayerImpl::performRequest@0x4282a3c`、`sndStop@0x4282538`、
   `sndOpen@0x428336c`、`DecoderSmz::reopen@0x426a64c`：记录进入前活动 row、
   是否重新 open 以及源采样位置。

只有同一次自然运行把“目标事件、全局 Direction 状态、835/836 request 或无新请求、
进入前活动播放器和源 phase”连起来，才能把 BGM 写入 production manifest。静态分析
已经把需捕获的字段缩到最小，但不能替代这项目标同 run 证据。

## 2026-07-16 APK-backed observer 与 PID3188 零输入预检

上述第 3–5 项现已进入通用 hunter。新增 5 个只读 hook、显式 attempt window、每窗
1024 条上限及溢出失败关闭；trace 内嵌每个 hook 的符号、地址、offset basis、模块路径
和命名字段 schema。MuMu 把未压缩 ELF 直接映射在
`split_config.arm64_v8a.apk` 下，而不是登记为独立 `libGameProc.so` module。首两次预检
因此正确在输入前失败，第二次还完整保存了 ready payload：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260716\evidence\target_bgm_upstream_pid3188_readonly_20260716_02\hunt_journal.jsonl
```

最终身份合同不再把 APK 路径冒充 `.so`：host 通过一次 `adb exec-out cat` 只读流同时
校验外层 split APK 83,710,748 bytes / SHA-256
`89ACC81D02FF63697603FCE2E5F4281850C092FA833FD8CF3E636B44AB624E24`，再按固定 ZIP
local header/data range 校验 STORED `lib/arm64-v8a/libGameProc.so` 79,683,640 bytes、
CRC32 `BBB59DED`、SHA-256
`5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF` 和 AArch64 ELF
header。JS 从 `fnGetAddrSdGmData - 0x424d474` 推导 ELF base，再核对 APK-backed mapping、
Frida base 及五个 export offset。

成功的 8 秒零输入检查点：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260716\evidence\target_bgm_upstream_pid3188_readonly_20260716_03\hunt_journal.jsonl
SHA-256 562A8F16864D6D0377CDC32E3F603338C4133A3DA37F4B5CF96D2204631C0F11
```

PID3188、前台 activity、外层 APK 与内部 ELF 全部精确匹配；13/13 primary hooks 安装、
0 unavailable、0 attach error、0 probe error，保留 973 条 bounded sound metadata、0 drop，
`adb_input_sent=false`。上游 attempt window 在主界面空闲的 8 秒内发出 0 条变更，这是
预期的 observer 健康检查，不是目标 BGM 结论。下一次有界自然回合可直接使用同一工具，
不再需要临时扩大 hook 范围。

### 首个实际回合的溢出修正与成功复验

首个单回合 `_04` 完整执行后按合同失败关闭：旧 signature 把 BGM hook 的唯一 call ID
纳入“状态”，并在 17 个对象间共享 DataSet signature，导致 960 条 DataSet、63 条
BGM_DIR 和 1 条 overflow，达到 1024 上限。journal 保留了五个已确认输入、credit
50→47、最终回到 state/mode 0/0 和完整溢出计数，但该回合不作为完整声音证据：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260716\evidence\target_bgm_upstream_pid3188_execute_20260716_04\hunt_journal.jsonl
SHA-256 CDF7D4A957A55B01866D12CDCF321517382DCF029AAF78F76DC5D1B72732075E
```

修复后 signature 排除 call ID，并按 hook + 对象指针分区；lottery hook 仍逐调用保留。
生产函数的可执行 Node 回归证明：同对象同状态重复 1000 次只发 1 条，跨对象和状态
变化才新增；1025 个独立状态仍在 1024 处准确失败。离线重放 `_04` 预计把 960/63
压成 31/2。hunter 也会在写 attempt summary 前关闭 window 并保存最终 counters，包含
error/dry-run 路径。

修复后的零输入 `_05`：window closed、20 emitted、0 dropped/error、无输入；journal
SHA-256 `CE9F8E503B3609FB65CC428577FC4B388FFD9D4F0CB0C5CA82CCE7FB26B09E09`。
随后只执行一个自然回合 `_06`，成功得到 non-target 完整证据：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260716\evidence\target_bgm_upstream_pid3188_execute_20260716_06\hunt_journal.jsonl
SHA-256 7D8FA6761DAD9AF55405EC845FB0CB53CB0DF62D59D7CEC4C2234E4A4C84826E
```

该回合 141 条 sound trace、0 drop/error，window closed、40/1024 emitted：37 条按对象
分区的 DataSet、2 条同一 BGM_DIR 对象的真实 1/1→0/0 状态、1 条 RlStart；credit
47→44，最终回到 0/0。它不是 SP Story target，也没有 `kind=0x2f` 或 835/836，但证明
新 observer 已能在真实回合中无溢出、无视觉猜测地记录上游状态。下一次目标命中无需
再修改这组 hook。
