# ac7205 代码权威复核与 v150 长片检查点（2026-08-24）

## 结论

- `ac7205` 的 DirInfo 母集共有 98 行、22 个事件；本轮按用户优先级闭合全部 21 个原生 `416x232` 事件。唯一 `512x288` 的 `ac7205_018` 已登记并延后，未混入本轮长片。
- 21 个事件按代码可达层、EventInfo/DirInfo 及内容语义排列为一个“全事件、全结果”编辑长片；它不宣称单局原生调度，但穷尽本系列 native416 可达结果。
- 25 个 authored DGM occurrence 归并为 23 个字节唯一来源；`L01/L01_lp`、`L03/L03_lp` 两对完全相同别名各只展示一次。完整 event presentation 之间没有精确重复。
- 旧的 `ac7205_008`、`ac7205_016` 短片不再作为当前独立审查目标；原始事件与媒体仍完整保留，本轮统一在 v150 长片中审查。

## 底层机制证据

IDA 静态证据把 MovieLayer 的关键值闭合到：

- `GetKey`：`0x42b12bc`；`key+0x1e bit0` 控制 persistence。
- `SetKeyTime`：`0x42b342c`；`key+0x1d` 的模式为：0=有限全场景、1=尾帧保持、2=全场景循环、3=从 Z2D 精确 loop point 循环、4=显式 key loop。
- ac7205 的 61 个 runtime layer binding 都有 mode/persistence 证据；渲染不再用文件名或目测猜循环。

音频 authority 逐 event 绑定 41 条保留音频（32 SE、9 voice）、9 条字幕；request226/sound551 的 3 个 BGM occurrence 被严格排除。字幕结束边界按 30fps 帧边界投影，避免跨进下一帧。

## 产物与状态

- 输入检查点：`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\ac7205_exhaustive_native416_longform_inputs_v149r3_20260824`
- 生产根：`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\no_bgm_editions_v150_ac7205_exhaustive_native416_authoritative_20260824`
- 单组人工审查入口：`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\manual_review_increment_v150_ac7205_exhaustive_20260824`
- 规模：1 个内容组，NONE/JP/ZH 三轨；3827 帧，约 127.566 秒，416x232、30fps、H.264/AAC 48kHz stereo。
- 自动 QA：通过；人工播放：待验收；投稿：未批准。
- 审查目录中的 MP4 是同盘 NTFS hardlink，未制造新的媒体物理副本。

精确路径、SHA-256、媒体验证与回滚记录见仓库 proposal 和 D: 两个 `VERIFICATION_RECORD.json`。
