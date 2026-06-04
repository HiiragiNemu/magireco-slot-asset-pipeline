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

### PLT 解析更新

继续解析 `.rela.plt` 后，关键调用已能还原为导入符号：

| PLT 地址 | 符号 |
| --- | --- |
| `0x449ca00` | `_Z10CTRLSNDLIBv` |
| `0x449d5e0` | `_ZN12C_CtrlSndLib17fnReqSndSoundCodeEPKch` |
| `0x4492820` | `_ZN9C_AnmBase17fnGetCallSignFlagEt` |
| `0x449d210` | `_ZN9C_AnmBase19fnClearCallSignFlagEt` |
| `0x4492190` | `_Z9MSTCOMCBKv` |
| `0x4492630` | `_Z6KEYDEFv` |
| `0x4492910` | `_ZN8C_KeyDef14fnGetSubKeyDefEt` |

`_ZN12C_CtrlSndLib17fnReqSndSoundCodeEPKch` demangle 后是：

```text
C_CtrlSndLib::fnReqSndSoundCode(char const*, unsigned char)
```

这使 `ac5408` 数字字符串的优先解释发生变化：它们应先视为“声音代码字符串”，而不是 OGG chunk index。

按声音代码理解：

- `1049`, `1050`, `1051`, `1052`, `1053`, `6825`, `6830`, `8032`, `26497` 在 `sound_id.dat` 中有 OGG 映射。
- `283`, `296`, `9078` 在 `sound_id.dat` 中没有同号声音资源映射。
- `9078` 对应的声音请求表行附近有 `EF230BC511AF008D5E5DD7934EF2.smz`，这更支持继续研究 SMZ 声音容器。
- `9078` 也能作为 OGG chunk index 映射到 `snd_04718_bank03_ogg_09078.ogg`，但由于调用名是 `fnReqSndSoundCode`，不能优先采用 OGG index 解释。

下一步应追 `C_CtrlSndLib::fnReqSndSoundCode` 的实现所在库，确认声音代码字符串如何落到 OGG/SMZ/request 表。

## 2026-06-05 - sound-code dispatch chain closed to zgSndReqCode

### Native 调用链

继续追 `C_CtrlSndLib`、`SndReceiveMessage`、`SndMngSetRequest`、`SndMngFrameFunction` 后，`ac5408` 的声音代码请求链路已经可以还原到低层声音系统：

```text
ac5408::fnSndRequest_BGM / fnPlaySND
  -> C_CtrlSndLib::fnReqSndSoundCode(char const*, unsigned char)
  -> C_CtrlSndLib::fnReqSndSoundCode(char const*, unsigned char, unsigned long)
  -> request type 2, code string copied into ST_ReqSndData
  -> C_CtrlSndLib::fnSendSndData(...)
  -> SndReceiveMessage(0x201, message)
  -> C_ReqGrpSnd::fnRegist / fnRequest
  -> SndMngSetRequest(0x201, message)
  -> SndMngFrameFunction()
  -> zgSndReqCode(code_string, param, 0)
  -> zgSndReqId(resolved_request_id, param, 0)
```

关键证据：

- `fnReqSndSoundCode` 会写入 request type `2`。
- `fnSendSndData` 对 type `2` 发送消息号 `0x201`，并把最多 0x40 字节的声音代码字符串复制进消息结构。
- `SndMngSetRequest` 的 jump table 显示消息低 8 位 `1` 和 `9` 都进入字符串声音代码队列分支。
- `SndMngFrameFunction` 对队列类型 `1/9` 调用 `zgSndReqCode`；对队列类型 `0` 调用 `zgSndReqHashCode`。
- `zgSndReqCode` 会通过声音系统对象 vtable `+0x58` 把 code string 转为内部 request id，然后调用 `zgSndReqId`。

### ac5408 旧 OGG 候选包

早期曾在 A 盘生成只复制不移动的 OGG 候选包：

```text
A:\magireco_bili_fulltest_20260603\sound_code_tests\ac5408_official_code_candidates
```

该包是按 `sound_resource_id == code` 做的启发式复制。结构化解析 `zg_snd_request_tbl.bin` 后已经确认：code string 映射到 request index，不等于 `sound_id.dat` 的 `sound_resource_id`。因此这个 OGG 包已降级为低置信度参考，不能作为官方音频合并依据。

### 判断

官方声音请求链路已经确认存在，但还不能全局自动把 OGG/SMZ 混入视频。原因是：

- code string 到 request id 的 vtable 解析仍需落到具体表文件。
- `9078`, `296`, `283` 这类未匹配 code 很可能依赖 SMZ 或另一张 code 表。
- 视频片段与声音请求之间还缺少时间轴或演出事件对应关系。

下一步应继续定位 `zgSndReqCode` 使用的 code-to-request-id 数据源，并优先对 `ac5408` 生成小规模“视频片段 + 官方候选音频”的人工审查包，而不是直接做全量自动 mux。

## 2026-06-05 - structured request table parser

### Native 结构确认

继续反汇编 `zg::snd::RequestCtrl::loadRequestTbl()` 和 `codeName2ReqId(char const*)` 后，确认 `zg_snd_request_tbl.bin` 的结构：

- 文件头是 0x40 字节，`u32[7]` 是 request 数量，本包为 10420。
- 每条 request 先读 0x48 字节：0x40 字节 code string、u32 `reqdata_count`、u32 `marker_count`。
- 每条 ReqData 先读 0x60 字节。
- 若 ReqData 的 signed `u32_22 % 5 != 0`，后面还有 0x0C fade 数据。
- 若 ReqData 的 signed `u32_23 % 3 == 2`，后面还有 0x28 ducking 数据。
- 每条 marker 是 0x24 字节。
- `codeName2ReqId` 查的是 `RequestCtrl + 0x28` 的 `std::map<string,uint32>`，返回 request index；找不到返回 `-1`。

新增命令：

```powershell
python magireco_asset_pipeline.py sound-request-struct-audit
```

输出：

```text
asset_manifests\sound_request_struct_requests.csv
asset_manifests\sound_request_struct_reqdata.csv
asset_manifests\sound_request_struct_summary.md
```

本次解析结果：

- requests: 10420
- ReqData rows: 11083
- requests without SMZ media: 58
- unique SMZ media names: 9779

### ac5408 结构化候选包

已在 A 盘生成新的结构化候选包：

```text
A:\magireco_bili_fulltest_20260603\sound_code_tests\ac5408_structured_code_to_smz
```

重点 code 的官方 request 表映射：

| code | request_id | first SMZ |
| --- | ---: | --- |
| `9078` | 2074 | `2A40747716A2B334129B4E859D42.smz` |
| `296` | 101 | none |
| `283` | 95 | none |
| `6825` | 1492 | `1622D09E2ADD3F9E609DCF959772.smz` |
| `26497` | 8297 | `219AB8B97C4E29291BB44B4EFBB2.smz` |
| `6830` | 1497 | `37288F4F4F95C8C8146FA2035B22.smz` |
| `8032` | 1678 | `6C42AA7341BB599291C9B7D35312.smz` |
| `1053` | 448 | `8A4A233E6BB8CFB14C79E1F234F2.smz` |
| `1052` | 447 | `B91EA87EC141173B3EF70D8B4052.smz` |
| `1051` | 446 | `22F05E94C422EDECF73A66E214B2.smz` |
| `1050` | 445 | `83D6634F254D3A407E8028CC1732.smz` |
| `1049` | 444 | `F53FACA2830323AB642C1AD01802.smz` |

### 判断

官方声音链路现在应优先按 code-to-request-table-to-SMZ 理解，而不是按 code-to-OGG 理解。下一步重点是把 request table 中的 SMZ 媒体名与 `OnDemandPack01\assets\smz.bin/smz_add.bin` 的 chunk 建立可验证对应，并研究 SMZ 解码或复用游戏内解码结果。
