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
- 每条记录可解析为 `8-byte hash + sample_count_u32 + zero tail`。
- request id 是记录序号，不是第三个 `u32` 字段。

当前统计：

| 项目 | 数量 |
| --- | ---: |
| 结构化 ReqData 唯一 SMZ 媒体名 | 9758 |
| 结构化 ReqData SMZ 引用 | 10944 |
| 结构化 ReqData 唯一 PCM 媒体名 | 21 |
| 结构化 ReqData PCM 引用 | 21 |
| `zg_snd_hashreq_tbl.bin` 记录 | 10420 |
| 通过记录序号关联到结构化 request 的 hash 行 | 10420 |
| 非零 `sample_count_u32` 行 | 9936 |
| 安装态 `smz.bin` chunk | 9752 |
| `loadFileSmz` relocated 名称 | 9752 |
| request 表有且安装态存在的 SMZ 名称 | 9752 |
| request 表有但安装态表无的 SMZ 名称 | 6 |
| 安装态有但 request 表未引用的 SMZ 名称 | 0 |
| 推测 mono chunk | 6826 |
| 推测 stereo chunk | 2926 |

### 限制

- `zg_snd_hashreq_tbl.bin` 的 8-byte hash 不是完整的 28 hex `.smz` 媒体名，不能直接当成文件名映射。
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
- unique media names: 9779
- after extension split: 9758 SMZ + 21 PCM

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

## 2026-06-05 - runtime SMZ name/chunk map closed

### Native relocation table

`DecoderSmz::open_stream()` 不按 hash 猜 chunk。它先从请求媒体名中取 basename，再遍历 native `loadFileSmz` 指针表做 `strcmp`，匹配成功后使用 `g_SMZDataAddress[i]..[i+1]` 作为 `smz.bin` 中的 offset/size。

`SndInitManager()` 会把 `smz_add.bin` 读入 `g_SMZDataAddress`，把 `pcm_add.bin` 读入 `g_PCMDataAddress`。

`loadFileSmz` 和 `loadFilePcm` 的表项由 `.rela.dyn` relative relocation 填充：

- `loadFileSmz`: 9752 个名称，匹配 9752 个 `smz.bin` chunk。
- `loadFilePcm`: 21 个名称，匹配全部 21 个 PCM request media。

### Corrected hash request table

`zg_snd_hashreq_tbl.bin` 是 `64 + 10420 * 16` 字节。记录按 request index 对齐：

- 8 bytes: hash
- u32: sample/play length field
- u32: zero tail

request id 是记录序号，不是第三个 `u32`。早期 `sound_hashreq_records.csv` 中把第三个字段命名为 request id 的判断已经修正。

### New outputs

`sound-media-audit` 现在会生成：

```text
asset_manifests\smz_name_chunk_map.csv
asset_manifests\pcm_name_table.csv
asset_manifests\smz_request_missing_from_installed_pack.csv
asset_manifests\sound_hashreq_records.csv
```

当前统计：

| 项目 | 数量 |
| --- | ---: |
| 结构化 SMZ media | 9758 |
| 结构化 SMZ references | 10944 |
| 结构化 PCM media | 21 |
| runtime SMZ names/chunks | 9752 |
| runtime PCM names | 21 |
| request 表有且安装态存在的 SMZ 名称 | 9752 |
| request 表有但安装态表无的 SMZ 名称 | 6 |
| 安装态有但 request 表未引用的 SMZ 名称 | 0 |
| 非零 `sample_count_u32` hash rows | 9936 |

6 个 request-only SMZ 名称是：

```text
1AF9169B573A7DC8A0DD38205512.smz
88D3F9E5BBF6C1FC58D1B3FD2DA2.smz
935011FC5F51AD6099D4882E17F2.smz
A4B82FCFB2F6A1B9655902525172.smz
B31749A51FD50294110A8BC28982.smz
C509F2C208EABC314652AF8DDC12.smz
```

### Decode status

临时样本切片和常见 MP3 skip 探测均失败；`.smz` 不是简单的“跳过 header 后得到 MP3”。下一步应优先还原/复用 native `DecoderSmz`，或者在模拟器运行态捕获声音输出。当前仍不能把外部 SMZ/OGG 自动 mux 到视频。

## 2026-06-05 - native WAV conversion entry found

### Symbols

`libGameProc.so` 暴露了可疑的内部 WAV 转换入口：

```text
zgSndCaptureConvertWav
zgSndCaptureConvertWavByHashCode
zg::snd::CaptureCtrlImpl::writeWaveFile(bool)
zg::snd::DecoderImpl::openForConvert(char const*, vector<TagZGSndMarker>&, SndDataHeader&)
```

`writeWaveFile()` 会拼接 `.wav` 后缀，用 `fopen(..., "wb")` 写文件，并输出 `[zgSnd] convert end` 日志。`DecoderImpl::openForConvert()` 会按媒体名分派到 `DecoderPcm::openForConvert()` 或 `DecoderSmz::openForConvert()`。

### Inferred call shape

`zgSndCaptureConvertWav(char const* mediaName, char const* outputDir, char const* outputStem)` 形式比较明确：它开启转换模式，调用 vtable `+0x128`，再关闭转换模式。

`zgSndCaptureConvertWavByHashCode(char const* code, char const* outputDir)` 先把 code 交给声音运行时对象解析 request，再取 request 的第一个媒体名，最后调用同一个 vtable `+0x128` 转 WAV。它依赖运行时全局声音对象已初始化；单独 `dlopen` Android so 不足以保证可用。

### Probe script

新增脚本：

```text
tools\frida_smz_wav_probe.py
```

用法：

```powershell
python tools\frida_smz_wav_probe.py --usb
python tools\frida_smz_wav_probe.py --usb --code 1049 --output-dir /sdcard/Download/magireco_wav_probe
```

当前没有执行 native 转换，因为 `adb connect 127.0.0.1:16384` 返回连接拒绝，模拟器目标不可用。本机已有 Frida 17.5.2；后续需要 Android 侧启动匹配版本 `frida-server` 后再验证。

## 2026-06-05 - RAMDISK correction pass

### User validation incorporated

用户确认旧目录仍左右反向，并指出 `review_audio\with_embedded_audio` 实际混有大量静音音轨。已将“有音频流”和“可听声音”拆开处理。

验证样本：

| path | mean_volume | max_volume | result |
| --- | ---: | ---: | --- |
| `Unclassified_Slices\main_video_2243.mp4` | -91.0 dB | -91.0 dB | silent audio track |
| `Unclassified_Slices\patch_video_1343.mp4` | -91.0 dB | -91.0 dB | silent audio track |
| `MultiCandidate_Slices\main_video_0097_candidates24.mp4` | -10.3 dB | 0.0 dB | audible embedded audio |

### Script changes

`magireco_asset_pipeline.py` 新增：

```powershell
python magireco_asset_pipeline.py hflip-videos --input-dir A:\magireco_bili_fulltest_20260603\videos --out-dir A:\magireco_bili_fulltest_20260603\videos_hflip --execute --encoder h264_nvenc --workers 2
python magireco_asset_pipeline.py review-special-videos --video-dir A:\magireco_bili_fulltest_20260603\videos_hflip --out-dir A:\magireco_bili_fulltest_20260603\review_special_hflip_audible --audio-volume --workers 4
python magireco_asset_pipeline.py convert-pcm-wav --input-dir A:\magireco_bili_fulltest_20260603\audio_assets\audio\pcm_raw --out-dir A:\magireco_bili_fulltest_20260603\audio_assets\audio\pcm_wav_48k_stereo --execute --overwrite --audio-volume --workers 4
```

`review-special-videos --audio-volume` 新增 `silent_audio_track` 分类。默认阈值为 `max_volume <= -60 dB`。

### Direction-correct output

首轮 NVENC hflip：

- input: 7801 MP4
- ok: 7031
- failed: 770
- failure cause: NVENC minimum frame dimension limit on very small videos, e.g. 80x312, 144x48, 144x64

随后删除 manifest 中 770 个失败的 0 字节输出，仅用 `libx264` 补跑缺失项：

- libx264 ok: 770
- skipped existing: 7031
- final MP4 count: 7801
- zero-byte output: 0

当前方向正确视频树：

```text
A:\magireco_bili_fulltest_20260603\videos_hflip
```

### Audible embedded audio audit

对 `videos_hflip` 全量执行 `review-special-videos --audio-volume`：

| class | count |
| --- | ---: |
| normal | 7096 |
| silent_audio_track | 315 |
| mostly_black_video | 259 |
| blackish_video | 131 |
| audio_only | 0 |
| no_video_stream | 0 |
| probe_failed | 0 |

真正可听内嵌音频只有 141 个，已硬链接到：

```text
A:\magireco_bili_fulltest_20260603\review_audio_hflip\audible_embedded_audio
```

### PCM conversion

`.pcmraw` 文件头部规律：

- 32 bytes custom header
- first little-endian u32 equals payload size
- payload is aligned for 16-bit stereo PCM
- dominant exported OGG sample rate is 48000 Hz

因此将 21 个 PCMRAW 转为 `s16le / 48000 Hz / stereo / skip 32 bytes` WAV：

```text
A:\magireco_bili_fulltest_20260603\audio_assets\audio\pcm_wav_48k_stereo
```

结果：

- ok: 21
- audible: 20
- silent: `pcm_00018.wav`

### Installed pull audit

`A:\magireco_installed_pull_20260603` 已复查。核心新增数据是安装态 assetpack：

```text
data_user_0\files\assetpacks\OnDemandPack01\31\31\assets\smz.bin
data_user_0\files\assetpacks\OnDemandPack01\31\31\assets\smz_add.bin
```

它们不在工程 `unpacked_assets\assets` 中，应该归档。用这组文件重跑 `sound-media-audit` 后结果稳定：

- runtime SMZ chunks: 9752
- structured SMZ media: 9758
- request-present installed SMZ: 9752
- request-only missing SMZ: 6
- runtime-only SMZ: 0
- PCM names: 21, all present

`pad.bin` 只记录 assetpack 路径；`ACCESS_DATA.xml` 只记录 `ACCESS=true`。当前未从安装态用户数据发现额外的视频命名、演出合并或音视频同步表。

### Frida native bridge attempt

本机 Frida client 为 17.5.2。已下载并测试：

```text
frida-server-17.5.2-android-x86_64
frida-server-17.5.2-android-arm64
```

当前 MuMu 设备：

```text
ro.product.cpu.abi = x86_64
```

游戏进程 `/proc/<pid>/maps` 显示实际游戏 native 库通过 native bridge 映射在：

```text
/system/lib64/arm64/...
```

结果：

- x86_64 frida-server 可以 attach 普通宿主进程，但只能枚举宿主侧模块，不能看到 arm64 `libGameProc.so`。
- arm64 frida-server 可以在 native bridge 下启动并显示版本，但 attach 时 server 关闭连接。
- 因此当前 MuMu/native-bridge 环境暂不能直接用 Frida 调用 `zgSndCaptureConvertWav*`。

脚本修正：

- `tools/frida_smz_wav_probe.py` 已兼容 Frida 17，改用 `Process.findModuleByName()` 和 `module.enumerateExports()`。
- 进程匹配已改为优先 `enumerate_applications()`，避免 Frida 17 的 `Process.identifier` 缺失问题。

下一步若继续 native WAV 方案，优先考虑真 arm64 Android 环境、支持 arm64 app 的模拟器镜像，或改走静态还原 `DecoderSmz`。
