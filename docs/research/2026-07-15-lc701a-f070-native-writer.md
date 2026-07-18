# 2026-07-15 LC701A `f070` native-writer closure

## 结论先行

本轮静态分析已经把 `PC 0x040a` 到 DirInfo3 的读取链闭合，也能离线、逐字节复现
LC701A 固件初始化解密。当前可以证明：

```text
VM[f070:f072] --PC 040a / 64 70--> r8 (HL)
VM[f072:f074] --PC 040c / EA 5E 72--> r6 (DE)
VM[f074:f076] --PC 040f / EA 4E 74--> r4 (BC)
PC 0412 / F7 --> RST 0x30 --> _USER_FC_CALL --> ED31
ED31 r8 low/high --既有运行时归因--> DirInfo3 raw[1]/raw[2]
```

因此，ID19 的目标 `raw[1] == 8` 已经收束成一个明确问题：在执行
`PC 0x040a` 前，谁最后把 `VM[f070]` 写成了 `8`。

同时也找到一个确定会覆盖 `f070` 的 native 路径：
`CplayData::LoadData(char const*) @ 0x421af2c` 从存档二进制逐字节恢复整个
`f000..f150` 区间。但它只能证明“持久化恢复 writer”存在，不能证明每次自然抽选中
产生当前六字节值的 writer 就是它。

尚未静态定位到固件内部最后一次修改 `f070..f075` 的具体指令/分支。完整解密镜像中
没有最直接的 `74 70`（把 r8 直接写到 `f070`）编码；但固件有通过 r8 间接寻址的
写指令、寄存器运算和复制指令，所以这项阴性结果不能扩张成“固件不会写 f070”。
下一步不应继续猜地址，而应执行本文末尾的最小只读 writer probe。

## 证据边界

本轮只读取静态文件和既有导出，没有向 MuMu 发送输入，没有替换函数返回值，也没有
写入游戏进程。分析对象为：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\native_analysis\libGameProc.so
```

校验值：

```text
libGameProc.so size:       79,683,640 bytes
libGameProc.so SHA-256:    5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF
encrypted firmware offset: 0x1577128
encrypted firmware size:   0xF150 (61,776 bytes)
encrypted firmware SHA-256:
  1A24F1F3665392214A96B4FE4867AA073D2E1F18AED1043B9F4DBEB35081FF49
initialized image SHA-256:
  AF9B32B0BE54982AAF706A0CFEA04FFCC5A376B7BB6E8145D1DD75E8EF139066
```

“initialized image”指按 `mnInitialization()` 的实际逻辑处理后的完整 `0xf150`
字节 VM 初始镜像，包含未 XOR 的间隙，不是只对看起来像代码的区间另做猜测。

## 固件初始化/解密可离线复现

`ID401::LC701A_SLOT::mnInitialization() @ 0x43f26e0` 先调用
`CLC701A::LC701A_Initial() @ 0x443b100`，再把
`libGameProc.so + 0x1577128` 的 `0xf150` 字节复制到对象内的 VM 基址
`this + 0x88`。`LC701A_Initial()` 把 halfword `0xf0ff` 写到对象起始处，
所以 direct-page 高字节 `this+1` 的初始值确为 `0xf0`。

函数使用以下 SIMD 常量生成 key stream：

```text
0x143eb50: [12, 13, 14, 15]
0x143eb60: [ 8,  9, 10, 11]
0x143ec50: [ 4,  5,  6,  7]
0x143ef20: [ 0,  1,  2,  3]
0x143fdc0: 00 04 08 0c 10 14 ... 3c
scalar:    0xc5d6e54a
```

这段向量代码化简后是从开头开始重复的四字节 XOR key：

```text
A9 52 A5 4A  A9 52 A5 4A  ...
```

精确等价的离线算法如下。一个容易造成 hash 不同的细节是：当首字节解密成
`FA` 或 `CB` 时，无论第二字节是否命中交换对，函数都会解密第二字节并跨过整对；
不能让下一轮再 XOR 第二字节。

```python
mem = bytearray(lib[0x1577128:0x1577128 + 0xF150])
key = (bytes.fromhex("A9 52 A5 4A") * ((0xF150 + 3) // 4))[:0xF150]

mem[0x0000:0x0040] = b"\xff" * 0x40
flags = 0
i = 0x40
while i <= 0x11ff:
    mem[i] ^= key[i]
    if mem[i] in (0xFA, 0xCB):
        first = mem[i]
        mem[i + 1] ^= key[i + 1]
        if first == 0xFA and mem[i + 1] == 0x8F:
            mem[i:i + 2] = b"\xCB\x33"
            flags |= 2
        elif first == 0xCB and mem[i + 1] == 0x33:
            mem[i:i + 2] = b"\xFA\x8F"
            flags |= 1
        i += 2
    else:
        i += 1

for lo, hi in (
    (0x1200, 0x12f3),
    (0x1343, 0xf143),
    (0xf143, 0xf150),
):
    for i in range(lo, hi):
        mem[i] ^= key[i]

assert flags == 3
```

注意 `0x12f3..0x1342` 不在上述 XOR 区间内。用此算法得到的 hash 正是前述
`AF9B...9066`。

## `PC 0x040a` 的六字节读取链

解密后的 `PC 0x0400` 窗口为：

```text
0400: 51 1c 14 3d 20 f9 50 84 10 e9 64 70 ea 5e 72 ea
0410: 4e 74 f7 e1 c1 10 e1 f8 64 0d 3e 09 f7 f0 53 16
0420: a2 57 c6 ca 49 82 20 f7 53 47 94 23 9a 3d d2 fb
```

主 opcode 长度表位于 `0x1586596`，每项三字节，第三字节是主 opcode 的
PC 长度。相关项为：

```text
opcode 64: 04 00 02
opcode 74: 04 00 02
opcode F7: 04 00 01
```

`EA` 是扩展前缀，主表项为零；其 handler 从 `PC+2` 取 direct-page 低地址，
所以上述两个 EA 指令各占三字节。

### `64 70`：从 `f070` 读入 r8

`ASM_0x64 @ 0x43f5774`：

1. 从 `this+0x20` 取 PC；
2. 从 `this+1` 取 direct-page 高字节（该 LC701A 状态为 `0xF0`）；
3. 从 `VM[PC+1]` 取低字节 `0x70`；
4. 从 `VM[0xf070]`、`VM[0xf071]` 读取 little-endian u16；
5. 写入 `this+0x08`，即 r8/HL。

等价式：

```text
r8 = LE16(VM[0xf070:0xf072])
```

### 两条 EA：继续读取 `f072..f075`

`ASM_0xEA5E @ 0x441cbc0` 把 direct-page 的 u16 写入 `this+0x06`
（r6/DE）；`ASM_0xEA4E @ 0x441c58c` 写入 `this+0x04`（r4/BC）。

```text
PC 040c: EA 5E 72 -> r6 = LE16(VM[f072:f074])
PC 040f: EA 4E 74 -> r4 = LE16(VM[f074:f076])
```

因此这不是三个互不相关的观察点，而是连续收集同一个六字节工作区。

### `F7`：进入 `0x30` helper

`ASM_0xF7 @ 0x43f8d3c` 把返回 PC 压入 VM stack，然后把 PC 设为 `0x30`。
`_USER_FC_CALL @ 0x43f2f64` 的相关 helper 分支已经静态闭合为：

```text
CALL(0x30) -> A5 -> ED31 -> F9 -> r6 = 0xf076 -> JPE(0x53)
```

`ASM_0xED31 @ 0x442b178` 依次把 r4、r6、r8 作为 u16 压入 VM stack。
仅凭静态栈布局不应猜最终 packet 字节顺序；既有运行时归因已经证明，在这条
helper 路径上：

```text
DirInfo3 raw[1] <- low byte of ED31 r8
DirInfo3 raw[2] <- high byte of ED31 r8
```

自然运行曾观察到 `ED31 r8=0x0400`，同一 packet 为
`raw[1]=0, raw[2]=4`。所以目标 `raw[1]=8` 需要在同一条路径上看到
`r8` 低字节为 `8`；不能把另一个 batch 的值拼进来。

## writer 搜索结果

### 固件初始状态和直接编码

初始化镜像中的：

```text
VM[f070:f076] = 00 00 00 00 00 00
```

这只说明 ROM/初始化镜像没有预置自然运行值，工作区值必须来自存档恢复或后续执行。

对完整解密镜像做原始字节搜索得到：

```text
64 70       -> 仅 0x040a 一处（direct u16 read into r8）
74 70       -> 0 处（direct u16 store from r8）
66 70       -> 0 处（直接构造 r8=f070 的明显形式）
F0 70       -> 0 处
F3 00 04    -> 0 处（直接 CALL 0x0400 的明显形式）
```

`ASM_0x74 @ 0x43f5a38` 确实会把 r8/HL little-endian 写到
direct-page 地址，因此 `74 70` 缺失排除了最简单的直接 writer。

但它没有排除间接 writer：

- `ASM_0x71`、`0x72`、`0x73`、`0x77` 都能把寄存器字节写到 r8/HL
  指向的 VM 地址；
- r8 可以由其他 load、算术、stack 和扩展 opcode 计算成 `0xf070`；
- 扩展 opcode 还包含寄存器到 direct address、word copy 和 block-copy 形态；
- 解密区间混有数据，原始 byte-pattern 命中本身也不等同于可达指令。

因此，当前静态证据只能表述为“未找到 obvious direct encoding”，不能表述为
“固件内没有 writer”。

### native 持久化 writer 已确定

`getTOPRWM_ADD() @ 0x43f25b0` 返回 `0xf000`，
`getWORKEND_ADD() @ 0x43f25b8` 返回 `0xf150`。

`CplayData::LoadData(char const*) @ 0x421af2c` 的循环在
`0x421af98..0x421afc4`：

```text
for index from 0 through (WORKEND - TOPRWM), inclusive:
    ID401::setWork(TOPRWM + index, loaded_binary[4 + index])
```

也就是它会逐字节写 `f000..f150`，必然包含 `f070..f075`。这是确定的
host/native writer，而且地址是循环计算出来的，所以在 `.text` 中搜索
`mov #0xf070` 找不到它是正常的。

完整 `.text` 中对 `ID401::setWork @ PLT 0x4490560` 的直接调用共 21 处：
一处是上述 `LoadData`，其余直接调用的可见常量地址为
`f004`、`f03e`、`f05d`、`f05e..f067`、`f069`、`f0c7` 等，未见
`f070`。五处 `setWork16` 直接调用使用 `f011` 或 `f05b`，同样不是
`f070`。这仍不能排除别的计算地址、wrapper 或直接内存 writer。

### 当前静态边界

现有静态证据无法区分以下三种来源中的哪一种提供了执行 `PC 0x040a` 前的最后值：

1. `CplayData::LoadData` 恢复的持久化六字节；
2. 本次 LC701A 固件执行中经 r8 间接写入或 block copy 更新的六字节；
3. native wrapper / `MemWrite*` / `setRWM*` 用计算地址写入的六字节。

既有运行时摘要记录过 ED31 的寄存器和后续 packet，也记录过 `fff0` packet-source
窗口，但没有围绕每一条 VM 指令保存 `f070..f075` 的 before/after。因此不能从旧
JSONL 可靠恢复“最后 writer”。这里是证据缺口，不应再用视觉结果或跨批次相关性填补。

## 最小只读 writer probe

目标是在不点击、不改寄存器、不替换返回值的前提下，只记录第一次改变
`VM[f070:f076]` 的调用/指令。推荐按以下顺序做一次短采样：

1. 在能取得 `CLC701A *this` 的 `FuncTableExe` 入口读取
   `this+0x88+0xf070` 的六字节快照；onLeave 再读一次。默认只输出六字节发生变化
   的行，避免恢复旧的高流量全指令日志。
2. 变化行至少记录：
   `pc_before`、opcode 前四字节、`pc_after`、r4/r6/r8、SP、六字节
   before/after、native return address 和 caller symbol。
3. 同时只读 hook 以下 API 的 onEnter/onLeave，记录实参地址、值和 caller：
   `ID401::setWork`、`setWork16`、`LC701A_SLOT::mn_setWork`、
   `mn_setWork16`、`setRWM`、`setRWM16`、`CLC701A::MemWrite`、
   `MemWriteW`、`MemWriteSP`、`CplayData::LoadData`。
4. 只为时间关联 hook `ASM_0x64`、`ASM_0xEA5E`、`ASM_0xEA4E`、
   `ASM_0xF7`、`ASM_0xED31`；这些 hook 不修改参数或返回值。
5. 同一个 execution episode 内要求观察到完整因果链：

```text
writer changes f070 low byte to 8
  -> PC 040a reads r8 low byte 8
  -> PC 0412 F7 / ED31
  -> same copied command-buffer batch has ID19 raw[1]=8
  -> same batch also has a legal ID24 stage/selector pair
```

如果 `FuncTableExe` before/after 显示变化，却没有任何公开 writer API 命中，则变化
来自固件 opcode；该行的 `pc_before` 和 opcode bytes 就是需要反汇编的确切分支。
如果变化先在 `LoadData` 出现且此后从未改动，则可把 persisted initialization 提升为
该次运行的直接来源证据。

页级 `MemoryAccessMonitor` 可能过于嘈杂，并且不如单线程 VM 的逐指令 before/after
稳定；它只应作为遗漏 native 直接写时的第二层手段。若调试器稳定，可对六字节使用
硬件 watchpoint，仍然只观察、不继续执行任何自动输入。

## 与既有结论的关系

本报告取代“`0xfff0` 是最终未解释源”的旧表述。`0xfff0` 是后续 packet staging
链的一部分；更上游、离 packet 生成更近的六字节工作源现在已经静态定位为
`f070..f075`。仍应同时阅读：

- `docs/research/2026-07-11-generic-runtime-timeline-and-lc701a-helpers.md`
- `docs/research/2026-07-04-id401-command-buffer-source.md`

本轮没有证明 SP Story 自然 gate 已经出现，也没有证明合法 ID19/ID24 可以跨 batch
组合。它只把最后未知量缩小为一个可由一次短、只读采样回答的 writer-provenance
问题。
