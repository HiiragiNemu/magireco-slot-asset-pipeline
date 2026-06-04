# Magireco Slot Asset Pipeline

这是一个本地资产审计与整理工具仓库，用于继续处理当前解包工程中的视频、图像、音频清单、命名、分类和候选拼合分析。

仓库只保存脚本和轻量文档，不保存 APK、解包素材、JADX 反编译源码、native 库、视频、图像或音频文件。原始游戏数据需要放在本地工作目录中，由 `.gitignore` 排除。

## 当前状态

已完成的本地审计结论见 [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md)。

下一步执行建议见 [docs/NEXT_STEPS.md](docs/NEXT_STEPS.md)。

主要结果：

- 视频 CRID chunk：7801
- 可唯一命名视频 chunk：483
- 多候选共享视频 chunk：607
- 直接无 GDB 候选视频 chunk：6711
- z2d 图像 chunk：12083
- z2d 名称引用：11733
- OGG chunk：9952
- `sound_id.dat` 音频映射记录：9951
- 含内嵌 `@SFA` 音频的视频 slice：456
- PCM chunk：21
- 视频连续序列候选：263，其中 175 组为高置信候选，但仍需复核共享 chunk 后再合并

## 不上传的数据

公开仓库不包含：

- `*.apk`, `*.obb`, `*.bin`, `*.dat`, `*.mp4`, `*.ogg`, `*.z2d`
- `downloaded_assets/`
- `unpacked_assets/`
- `unpacked_base/`
- `unpacked_lib/`
- `jadx_audit/`
- `asset_manifests/`
- 临时导出、最终视频、JADX GUI 工具包

这些内容体积很大，并且可能包含专有游戏数据。需要时在本地重新生成。

## 常用命令

生成基础资产清单：

```powershell
python magireco_asset_pipeline.py manifest
```

生成 Java/smali/native/GDB/m_info/sound_id 交叉审计报告：

```powershell
python magireco_internal_audit.py
```

音频导出 dry-run，按 `sound_id.dat` 给 OGG 命名：

```powershell
python magireco_asset_pipeline.py export-audio --sound-id-names --limit 5
```

实际导出音频：

```powershell
python magireco_asset_pipeline.py export-audio --sound-id-names --execute
```

视频整理 dry-run：

```powershell
python magireco_asset_pipeline.py organize-videos
```

对已导出的 MP4 生成序列复核报告，不合并视频：

```powershell
python magireco_asset_pipeline.py video-review --video-dir D:\MagiaRe_RAMDISK_Backup_20260603_032042\magireco_final_mp4_videos --write-concat-plans
```

解析 `zg_snd_request_tbl.bin`，生成声音请求 ID、描述标签、候选 `.smz/.pcm` 媒体名与 `sound_id.dat` 的关联审计：

```powershell
python magireco_asset_pipeline.py sound-request-audit
```

审计声音请求表中的 `.smz/.pcm` 媒体名、`zg_snd_hashreq_tbl.bin` 哈希请求表，以及可选的安装态 `smz.bin/smz_add.bin`：

```powershell
python magireco_asset_pipeline.py sound-media-audit --smz-bin A:\magireco_installed_pull_20260603\data_user_0\files\assetpacks\OnDemandPack01\31\31\assets\smz.bin --smz-add A:\magireco_installed_pull_20260603\data_user_0\files\assetpacks\OnDemandPack01\31\31\assets\smz_add.bin
```

从已有 native 字符串清单中提取声音请求、SMZ 表和 `EVT_ac` 事件标签证据：

```powershell
python magireco_asset_pipeline.py native-sound-video-audit
```

扫描已导出的 MP4，收集纯音频、无视频流、全黑或近黑画面复核候选：

```powershell
python magireco_asset_pipeline.py review-special-videos --video-dir A:\magireco_bili_fulltest_20260603\videos --out-dir A:\magireco_bili_fulltest_20260603\review_special
```

按 `MultiCandidate_Slices` 中连续的 `main_video_NNNN_candidatesX` 切片做候选数合并测试：

```powershell
python magireco_asset_pipeline.py merge-candidate-runs --video-dir A:\magireco_bili_fulltest_20260603\videos --out-dir A:\magireco_bili_fulltest_20260603\merge_tests\candidate_runs_command_execute_hflip_video_only --execute --hflip --drop-audio --probe
```

生成面向 B 站整理的标题、标签和说明候选报告：

```powershell
python magireco_asset_pipeline.py bili-metadata-audit
```

## 外部工具

- Python 3.10+
- FFmpeg，用于视频封装、音频合并、候选拼接
- JADX，用于生成本地 `jadx_audit/base_src_only`
- 可选：`requests`, `tqdm`, `mitmproxy`

## 安全原则

默认命令尽量 dry-run。会移动、复制、导出或合并文件的步骤需要显式加 `--execute`。

视频拼合目前只生成候选，不自动批量合并。原因是大量 `acXXXX_NNN` 名称共享同一 CRID chunk，必须先确认共享片段是否代表同一实际画面或通用片段。
