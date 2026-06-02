# Next Steps

更新时间：2026-06-03

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

检查样本输出：

```powershell
Get-ChildItem -Recurse final_mp4_videos -Filter *.mp4 | Select-Object FullName,Length
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

## 下一轮自动化建议

下一轮应新增一个 `video-review` 命令：

```powershell
python magireco_asset_pipeline.py video-review --limit 200
```

建议功能：

- 扫描已导出的 MP4
- 生成 `video_review.csv`
- 用 ffprobe 记录时长、分辨率、codec、音轨
- 用 ffmpeg 提取首帧/中间帧
- 对同一 `sequence_key` 的候选做排序和连续性报告
- 给出 `safe_to_merge`, `needs_manual_review`, `do_not_merge` 三类结论

这个命令是目前最值得继续开发的自动化步骤。
