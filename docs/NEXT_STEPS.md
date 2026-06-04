# Next Steps

更新时间：2026-06-05

## 是否还有内容值得上传

建议上传：

- 工具脚本
- 状态文档
- 下一步执行手册
- 清单字段说明或 schema 文档

不建议上传：

- APK、解包素材、JADX 反编译源码、native 库
- `asset_manifests/*.csv`
- `asset_manifests/internal_audit/*.csv`
- 已导出视频、图像、音频

原因：

- 体积大，容易超过 GitHub 普通仓库合理使用范围
- 包含专有资源名、素材结构和反编译内容
- 清单可由脚本本地再生成，上传收益低

## 推荐下一步

下一步目标不是立即全量导出，而是建立“可验证的批处理闭环”：

1. 导出少量视频样本
2. 对样本做 ffprobe 元数据检查
3. 生成首帧/关键帧截图
4. 按 `video_sequence_candidates.csv` 检查长序列是否真实连续
5. 对共享 chunk 做画面 hash、时长、分辨率、音轨一致性比对
6. 确认规则后，再批量整理和合并

## 建议你亲自审阅的文件

优先审阅：

```text
docs/PROJECT_STATUS.md
asset_manifests/video_candidates.csv
asset_manifests/internal_audit/video_sequence_candidates.csv
asset_manifests/sound_id_records.csv
asset_manifests/z2d_name_candidates.csv
```

审阅重点：

- `video_candidates.csv`
  - 看 `candidate_count`
  - `candidate_count = 1` 才适合直接命名
  - `candidate_count > 1` 不能直接归属单一演出

- `video_sequence_candidates.csv`
  - 看 `sequence_key`
  - 看 `confidence`
  - 看 `recommendation`
  - `review_before_merge_shared_chunks` 必须复核后再合并

- `sound_id_records.csv`
  - 看 `sound_resource_id`
  - 看 `ogg_chunk_index`
  - 看 `sound_bank`
  - 这张表可作为 OGG 命名基础

- `z2d_name_candidates.csv`
  - 看 z2d 是否能按 `acXXXX` 合理分组
  - 大量非 `ac` 或 unclassified 图像应保留为系统/通用资源

## 建议由我自动化的工作

适合自动化：

- 生成视频样本输出目录
- 对样本跑 `ffprobe`
- 提取首帧/中间帧截图
- 生成视频体积、时长、分辨率、codec、音轨统计 CSV
- 对候选序列建立复核报告
- 导出 OGG 并按 `sound_id.dat` 命名
- 建立只复制不移动的分类目录

暂不应自动化：

- 全量移动原视频
- 全量自动拼接视频
- 将多候选 chunk 强行命名为单一演出
- 把 z2d 当作 PNG/JPG 导出

## 建议本地执行顺序

先重新生成清单：

```powershell
python magireco_asset_pipeline.py manifest
python magireco_internal_audit.py
```

先导出小批量视频样本，不合并：

```powershell
python magireco_slot_video_extractor.py --package main --start-index 607 --limit 20 --workers 4
```

说明：

- `main:607` 起是一批唯一候选命名样本，适合验证 MP4 生成、翻转、音频封装和命名逻辑
- 不加 `--merge`，避免在未复核前自动拼合
- 当前 C 盘剩余空间较低，不建议直接全量导出
- 这一批样本原始 slice 不含 `@SFA` 音频，因此导出的 MP4 没声音是正常现象

用一个含内嵌音频的样本验证音频封装：

```powershell
python magireco_slot_video_extractor.py --package main --start-index 97 --limit 1 --workers 1
```

扫描全部视频 slice 是否含内嵌 `@SFA` 音频：

```powershell
python magireco_asset_pipeline.py video-audio-scan
```

检查样本输出：

```powershell
Get-ChildItem -Recurse final_mp4_videos -Filter *.mp4 | Select-Object FullName,Length
```

如果使用 RAMDISK，例如 `A:`，建议把输出和临时目录放到 RAMDISK：

```powershell
python magireco_slot_video_extractor.py --package main --start-index 607 --limit 20 --workers 4 --final-dir A:\magireco_final_mp4_videos --temp-dir A:\magireco_temp_usm_slices
```

全量导出前建议先只跑 `main`，仍不加 `--merge`：

```powershell
python magireco_slot_video_extractor.py --package main --workers 8 --final-dir A:\magireco_final_mp4_videos --temp-dir A:\magireco_temp_usm_slices
```

检查音频命名 dry-run：

```powershell
python magireco_asset_pipeline.py export-audio --sound-id-names --limit 20
```

如 dry-run 正常，再执行音频导出：

```powershell
python magireco_asset_pipeline.py export-audio --sound-id-names --execute
```

视频整理先保持 dry-run：

```powershell
python magireco_asset_pipeline.py organize-videos
```

不要先执行：

```powershell
python magireco_slot_video_extractor.py --merge
python magireco_asset_pipeline.py organize-videos --execute --merge
```

原因是当前视频序列候选仍需复核共享 chunk。

## 已完成的下一轮自动化

已新增 `video-review` 命令：

```powershell
python magireco_asset_pipeline.py video-review --video-dir D:\MagiaRe_RAMDISK_Backup_20260603_032042\magireco_final_mp4_videos --write-concat-plans
```

该命令会：

- 读取已导出 MP4 的 `ffprobe` 审计结果
- 结合 `video_candidates.csv` 和 `video_sequence_candidates.csv`
- 生成序列复核表、逐项表、唯一连续片段表
- 可选生成 ffconcat 预览列表
- 不移动、不删除、不生成最终合并视频

当前结果：

- 视频序列候选：263
- 涉及共享 chunk、需复核：261
- 存在同名映射歧义：2
- `ac0902` 唯一连续预览片段：26
- 已在 D 盘备份目录生成 26 个 `ac0902` 预览拼合 MP4，全部 `ffprobe` 通过
- `ac0902_*` 唯一命名视频共 483 个，全部没有内嵌音轨
- 当前 7801 个 MP4 均有视频流，未发现真正“只有音频无画面”的 MP4
- 456 个带内嵌音频的 MP4 中，仅发现少量黑画面/近黑画面片段

## 当前下一步任务

下一步应优先做三件事：

1. 视觉复核 `ac0902` 的 26 个预览拼合视频，判断这些片段是否确实连续、是否存在明显断点或画面错序。
2. 开始外部音频关联审计，重点查找 native/event 表中 `sound_id`、OGG bank、演出名或 `acXXXX` 之间的映射。
3. 使用 `sound-request-audit` 生成声音请求表，按请求标签筛选可能与演出相关的 OGG/PCM，再回查 native/event 调度来源。

声音请求表审计命令：

```powershell
python magireco_asset_pipeline.py sound-request-audit
```

已确认该命令会生成：

```text
asset_manifests/sound_request_audit.csv
asset_manifests/sound_request_summary.md
```

优先人工查看：

```text
asset_manifests/sound_request_audit.csv
```

重点字段：

- `sound_resource_id`
- `request_text`
- `request_label`
- `sound_bank`
- `suggested_name`
- `ogg_duration_sec`
- `nearest_media`

注意：`nearest_media` 只是声音表内的邻近 `.smz/.pcm` 候选，不能直接等同于视频同步关系。

## 已完成的 B 站全量测试

全量输出目录：

```text
A:\magireco_bili_fulltest_20260603\videos
```

特殊复核目录：

```text
A:\magireco_bili_fulltest_20260603\review_special
```

结果：

- 输出 MP4：7801
- 有视频无音轨：7345
- 有视频有音轨：456
- 纯音频/无视频 MP4：0
- 全黑采样视频：133
- 近黑采样视频：259

优先人工审查：

```text
A:\magireco_bili_fulltest_20260603\review_special\blackish_video
A:\magireco_bili_fulltest_20260603\review_special\mostly_black_video
A:\magireco_bili_fulltest_20260603\review_special\special_video_audit.csv
asset_manifests/bilibili_video_metadata_candidates.csv
asset_manifests/bilibili_sound_label_candidates.csv
asset_manifests/bilibili_metadata_summary.md
```

下一步技术任务：

1. 从 `bilibili_video_metadata_candidates.csv` 挑选高价值长序列，优先处理 `confidence=high` 且人工确认画面连续的项目。
2. 从 `bilibili_sound_label_candidates.csv` 按 `演出`、`セリフ`、`WIN`、`CZ`、角色名筛选可能音频。
3. 继续审计 native/event 调度，寻找视频序列与 `sound_resource_id` 的真实播放关系。
4. 最终面向 B 站输出时，将已确认成品统一转为 `h264 + aac`，当前测试保留 `alac` 是为了不损失内嵌音频。

暂不建议：

- 全局合并 263 个序列
- 给共享 chunk 强行指定单一演出名
- 把无内嵌音轨视频和 OGG 按时长或文件序号硬匹配

## 已完成的候选数合并测试

已新增 `merge-candidate-runs` 命令，用于复现按 `candidatesX` 连续段的测试合并：

```powershell
python magireco_asset_pipeline.py merge-candidate-runs --video-dir A:\magireco_bili_fulltest_20260603\videos --out-dir A:\magireco_bili_fulltest_20260603\merge_tests\candidate_runs_command_execute_hflip_video_only --execute --hflip --drop-audio --probe
```

本轮结果：

- 输入：`MultiCandidate_Slices` 607 个 MP4
- 输出：73 个 MP4
- 真正合并段：29
- 单片保留：44
- 示例：`main_video_0071-0099_candidates24.mp4`
- 该示例来自 29 个源片段，时长 48.100 秒，源片段中 3 个带内嵌音频

注意：

- 当前输出是 `--drop-audio` 的 video-only 测试版，因为同一合并段内可能混有有音轨/无音轨源片段。
- 当前输出加了 `--hflip`，用于校正用户确认的左右镜像问题。
- 该测试适合作为人工判断“减少视频数量是否可观看”的材料，不是最终投稿版。

已归档到：

```text
D:\MagiaRe_RAMDISK_Delta_20260604_002343\merge_tests\candidate_runs_command_execute_hflip_video_only
```

## 安装态拉取后的下一步

已确认：

- 模拟器安装态 APK/split APK 与本地 APK/split APK 哈希一致
- 模拟器安装态 main/patch OBB 与本地下载 OBB 哈希一致
- Python 复刻下载得到的主资源没有发现缺失
- 新增运行态资源主要是 Play Asset Delivery 的 `OnDemandPack01`

下一步建议：

1. 继续研究 `OnDemandPack01\assets\smz.bin` 与 `smz_add.bin` 的声音 chunk header 和解码方式。
2. 继续在 `libGameProc.so` / binary 表里查找视频播放事件与 `sound_resource_id`、`zg_snd_hashreq_tbl.bin` request id 或 `.smz` hash 的同源调度结构。
3. 对已带内嵌音频的 456 个 MP4，先做可投稿候选复核；这部分不需要外部 OGG 匹配。
4. 对无内嵌音频但明显是演出长段的视频，只在找到官方调度证据后再合并 OGG/PCM。

已归档到：

```text
D:\MagiaRe_RAMDISK_Delta_20260604_002343\installed_pull_delta
```

## 声音媒体/SMZ 的下一步

已完成的命令：

```powershell
python magireco_asset_pipeline.py sound-media-audit --smz-bin A:\magireco_installed_pull_20260603\data_user_0\files\assetpacks\OnDemandPack01\31\31\assets\smz.bin --smz-add A:\magireco_installed_pull_20260603\data_user_0\files\assetpacks\OnDemandPack01\31\31\assets\smz_add.bin
```

优先审阅：

```text
asset_manifests/sound_media_summary.md
asset_manifests/sound_hashreq_records.csv
asset_manifests/smz_chunk_header_audit.csv
asset_manifests/smz_name_chunk_map.csv
asset_manifests/smz_request_missing_from_installed_pack.csv
asset_manifests/pcm_name_table.csv
asset_manifests/sound_request_audit.csv
asset_manifests/native_sound_video_summary.md
asset_manifests/native_sound_video_evidence.csv
```

下一步技术任务：

1. 以 `smz_name_chunk_map.csv` 作为官方 SMZ 名称到 `smz.bin` chunk 的基准表；这一步已不需要继续靠 hash 猜测。
2. 研究 `DecoderSmz`：优先尝试最小 native 解码 harness；若成本过高，再考虑用模拟器运行态捕获声音输出。
3. 使用 `sound_request_struct_reqdata.csv` 建立 code -> request id -> SMZ media -> chunk index 的候选表，不再把 code 直接等同于 `sound_id.dat` 的 `sound_resource_id`。
4. 单独审查 6 个 request 表存在但安装态 `loadFileSmz` 不存在的 SMZ 名称，判断是否是空请求、兼容遗留项或另一个包中的资源。
5. 继续追 native/event 调度，寻找视频序列与 request code、request id 或 SMZ media 的同源关系。
6. 对 `ac5102` 的 45 条 `EVT_ac` 标签建立事件名到视频素材的人工复核表。
7. 暂时不要把 `.smz` 或 OGG 按文件序号、时长、相邻编号自动合并到视频；目前没有同步证据。
8. 对 `ac5408` 先生成小规模“视频片段 + 官方 SMZ 候选音频”的人工审查包，前提是 SMZ 已能解码或可从运行态捕获为 WAV/OGG。
