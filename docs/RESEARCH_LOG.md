# Research Log

本文件记录已完成的研究结论和可复现命令，避免后续重复推理。只记录脚本、清单和结论，不记录大体积游戏素材。

## 2026-06-05 - RAMDISK restore and sound media audit

### RAMDISK 状态

用户已将上一轮 RAMDISK 结果恢复到 A 盘，当前可用目录：

```text
A:\magireco_bili_fulltest_20260603
A:\magireco_installed_pull_20260603
```

复核结果显示：

- `A:\magireco_bili_fulltest_20260603\videos` 仍包含全量 MP4 输出。
- `A:\magireco_bili_fulltest_20260603\audio_assets` 仍包含已导出的 OGG/PCM。
- `A:\magireco_installed_pull_20260603` 仍包含 MuMu 安装态拉取内容和 `OnDemandPack01`。

### 新增命令

新增 `sound-media-audit`：

```powershell
python magireco_asset_pipeline.py sound-media-audit --smz-bin A:\magireco_installed_pull_20260603\data_user_0\files\assetpacks\OnDemandPack01\31\31\assets\smz.bin --smz-add A:\magireco_installed_pull_20260603\data_user_0\files\assetpacks\OnDemandPack01\31\31\assets\smz_add.bin
```

该命令读取：

- `asset_manifests\sound_request_audit.csv`
- `unpacked_assets\assets\zg_snd_hashreq_tbl.bin`
- 可选安装态 `smz.bin`
- 可选安装态 `smz_add.bin`

该命令输出：

- `asset_manifests\sound_hashreq_records.csv`
- `asset_manifests\smz_chunk_header_audit.csv`
- `asset_manifests\sound_media_summary.md`

### 关键结论

`OnDemandPack01\assets\smz.bin` 和 `smz_add.bin` 应优先按声音媒体容器继续研究。

依据：

- 声音请求表附近出现 9758 个唯一 `.smz` 媒体名。
- 安装态 `smz_add.bin` 定义 9752 个 chunk。
- 两者数量高度接近，且同属声音请求链路附近；这比“图像/模型容器”的初步判断更合理。

`zg_snd_hashreq_tbl.bin` 当前可按以下结构审计：

- 前 64 字节是 16 个 little-endian `u32` header。
- header 中包含 `48000`，很可能是采样率线索。
- header 中包含 `10420`，与后续 16 字节记录数一致。
- 每条记录可解析为 `8-byte hash + request_id + zero tail`。

当前统计：

| 项目 | 数量 |
| --- | ---: |
| 声音请求表附近唯一 `.smz` 媒体名 | 9758 |
| 声音请求表附近唯一 `.pcm` 媒体名 | 21 |
| 声音请求表附近媒体引用总数 | 33601 |
| `zg_snd_hashreq_tbl.bin` 记录 | 10420 |
| 哈希表唯一 request id | 4689 |
| 可关联到已解析声音请求行的哈希记录 | 3104 |
| 可关联到已解析声音请求行的 request id | 1091 |
| 安装态 `smz.bin` chunk | 9752 |
| 推测 mono chunk | 6826 |
| 推测 stereo chunk | 2926 |

### 限制

- `zg_snd_hashreq_tbl.bin` 的 8-byte hash 不是完整的 28 hex `.smz` 媒体名，当前不能直接建立 `.smz filename -> request_id` 的最终映射。
- 抽样 `.smz` chunk 不能直接被 `ffprobe` 识别。
- 这次审计没有证明外部音频和具体视频片段之间的同步关系。
- 不能把 OGG、PCM 或 `.smz` 按时长、编号或相邻关系强行合并到视频。

### 下一步

1. 继续研究 `.smz` chunk header 和可能 codec。
2. 在 native/JADX/smali 里追查 `zg_snd_hashreq_tbl.bin`、`smz`、`sound_resource_id`、request id 与视频调度的关系。
3. 对已有官方标签的声音请求先建立人工候选池，用于 B 站标题、说明、标签和后续手工试听。
4. 只对 456 个自带内嵌音轨的 MP4 先推进有声投稿候选；无内嵌音轨视频等待同步证据。

## 2026-06-05 - Native sound/video string evidence

### 新增命令

新增 `native-sound-video-audit`：

```powershell
python magireco_asset_pipeline.py native-sound-video-audit
```

该命令读取：

- `asset_manifests\internal_audit\native_strings.csv`

该命令输出：

- `asset_manifests\native_sound_video_evidence.csv`
- `asset_manifests\native_sound_video_summary.md`

### 关键结论

当前 native 字符串证据统计：

| 类别 | 数量 |
| --- | ---: |
| `sound_media_table` | 6 |
| `sound_request_symbol` | 16 |
| `event_label` | 588 |
| `ac_play_method` | 15 |

明确看到的资源/表：

- `smz.bin`
- `smz_add.bin`
- `zg_snd_hashreq_tbl.bin`
- `sound_id.dat`
- `ogg.bin`
- `ogg_add.bin`

明确看到的声音/事件线索：

- Java/smali 层只有 `SndMng.nsmSndReq(int)` native 入口。
- `ac5406`, `ac5407`, `ac5408` 有专用 `fnSndRequest_BGM` native 符号。
- `ac1101` 至 `ac1206` 以及 `ac5209` 出现在 `C_ObjNml::fnSndRequest_BGM_DIR()` 证据中。
- `ac5102` 有 45 条 `EVT_ac` 事件标签，但没有直接字符串级 `sound_request_symbol`。
- `ac0902`, `ac4921`, `ac0904`, `ac3409`, `ac3410` 当前没有直接字符串级声音请求或 `EVT_ac` 证据。

### 判断

这证明 native 里确实存在演出事件与声音请求的同层线索，但目前仍只是符号/字符串级证据，不是最终同步表。下一步应优先追 `ac5406-5408`，因为它们同时有 `fnSndRequest_BGM`、`fnPlaySND`/`fnPlayAnm` 类方法和 `EVT_ac` 标签，最适合作为还原声音请求链的样本。

## 2026-06-05 - ac5408 symbol and disassembly sample

### 工具状态

本机 PATH 中没有可直接使用的 `llvm-objdump`、`objdump`、`readelf` 或 `nm`。本轮用纯 Python 解析 `libGameProc.so` 的 ELF header、program header 和 `.dynsym`，并临时安装 Capstone 到：

```text
A:\TEMP\pydeps_capstone
```

该目录不属于仓库，不提交。

### 符号表结论

`libGameProc.so` 保留 `.dynsym`，可以拿到 `ac5406-5408` 的函数地址和大小：

| 函数 | 地址 | 大小 |
| --- | ---: | ---: |
| `C_ac5406::fnSndRequest_BGM()` | `0x43e9eb4` | 4 |
| `C_ac5407::fnSndRequest_BGM()` | `0x43ea9e8` | 4 |
| `C_ac5408::fnSndRequest_BGM()` | `0x43ec088` | 88 |
| `C_ac5408::fnPlaySND()` | `0x43eaef0` | 836 |
| `C_ac5408::fnSetEventCode()` | `0x43ead34` | 344 |

反汇编确认：

- `ac5406::fnSndRequest_BGM()` 是单条 `ret`。
- `ac5407::fnSndRequest_BGM()` 是单条 `ret`。
- `ac5408::fnSndRequest_BGM()` 有实际逻辑，会加载数字字符串 `9078` 并调用内部函数。

### ac5408 数字字符串

`ac5408` 声音相关函数中出现以下数字字符串：

| 来源函数 | 数字字符串 |
| --- | --- |
| `fnSndRequest_BGM` | `9078` |
| `fnPlaySND` | `296`, `283`, `6825`, `26497`, `6830`, `8032`, `1053`, `1052`, `1051`, `1050`, `1049` |

按现有声音清单查询：

- `6825`, `26497`, `6830`, `8032`, `1053`, `1052`, `1051`, `1050`, `1049` 都能作为 `sound_resource_id` 映射到 OGG。
- `296`, `283`, `9078` 不能作为有 OGG 的 `sound_resource_id`，但能作为 `ogg_chunk_index` 映射到其他声音资源。
- `9078` 作为 OGG chunk index 对应 `snd_04718_bank03_ogg_09078.ogg`，标签是 `復活成功【WIN】_019`；但作为 request id 9078 当前没有 `sound_id.dat` 映射。

### 判断

`ac5408` 是当前最有价值的反汇编样本，但这些数字字符串的语义仍未确定。它们可能是声音请求 ID、OGG index、hash/request 参数或内部事件参数。下一步必须继续追 `0x449d5e0`、`0x449ca00`、`0x4492820` 等内部调用目标，而不是直接把这些 OGG 合并到视频。
