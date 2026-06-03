# Project Status

更新时间：2026-06-03

## 审计范围

已检查本地 APK/解包内容、JADX 输出、smali、native 字符串、GDB、`m_info.dat`、`sound_id.dat` 和现有提取脚本。

JADX CLI 输出目录：

```text
jadx_audit/base_src_only
```

JADX 输出文件数：1142。

## 关键代码层结论

Java/smali 层显示：

- `SlotMainActivity` 将 `cri.bin`, `cri2.bin`, `cri3.bin` 以及对应 add 表交给 `SysMng`
- `SysMng` 调用 native `nsysmSetCriFileNames` 和 `nsysmLoadOffset`
- 演出调试入口 `DebugProd.dispatchData(int,int,int,int,int)` 也是 native
- `DebugDispNameList` 和 `DebugProd` 提供演出标签，但不包含完整视频播放/拼合逻辑

native 层显示：

- `libARES.so` 包含 `CBinCtrl`, `LoadOffset`, `GetFileOffset`, `CRI_FUSION_FILENAME`, `MARGE_INFO_FILENAME`, `OGG_FUSION_FILENAME`, `SOUND_ID_FILENAME`
- `libGameProc.so` 含大量 `acXXXX`、图像/演出/音频资源字符串
- 实际资源选择、offset 读取、融合包处理和可能的演出调度主要在 native

## 资产统计

基础清单：

| 类型 | 数量 |
| --- | ---: |
| CRID 视频 chunk | 7801 |
| 唯一视频命名 | 483 |
| 多候选视频 chunk | 607 |
| 无直接视频候选 | 6711 |
| z2d chunk | 12083 |
| z2d 名称引用 | 11733 |
| OGG chunk | 9952 |
| `sound_id.dat` 记录 | 9951 |
| 含内嵌 `@SFA` 音频的视频 slice | 456 |
| PCM chunk | 21 |
| `m_info.dat` 记录 | 1084 |

内部审计：

| 项目 | 数量 |
| --- | ---: |
| Java/smali 关键文本引用 | 516 |
| native 方法声明 | 130 |
| native 相关字符串 | 41814 |
| native `ac` token | 34441 |
| native 序列候选 | 22979 |
| 视频序列候选 | 263 |
| 高置信视频序列候选 | 175 |
| 图像 `ac` 分组 | 256 |

## 视频命名与拼合判断

当前视频命名必须保守：

- 483 个 CRID chunk 可以唯一命名
- 多候选共享 chunk 不能强行命名为单一 `acXXXX_NNN`
- `ac0902`, `ac4921`, `ac0904`, `ac3409`, `ac3410`, `ac5102` 等存在长连续编号
- 这些长序列高置信，但很多 chunk 被多个演出名共享，所以只适合进入复核队列，不适合无条件自动拼合

当前建议：

- 先导出小样本视频，按 `video_sequence_candidates.csv` 人工或脚本核验画面连续性
- 对共享 chunk 建立画面 hash/时长/分辨率/音轨一致性检查后，再进入自动合并
- 未唯一命名的视频保留 `package + index`，避免误标

## 图像分类判断

z2d 的 GDB 名称引用足够多，可以按嵌入的 `acXXXX` 分组。

仍需注意：

- 大量 unclassified 图像可能是系统 UI、通用部件或非 `ac` 前缀资源
- 不应尝试伪装成 PNG；当前只导出 raw `.z2d`

## 音频判断

`sound_id.dat` 已解析为：

- 7 字节头
- 后续 9951 条记录
- 每条 12 字节
- 包含声音资源号、OGG chunk index、bank/category、固定 marker

OGG chunk 0 未映射，可能是保留项。chunk 1 起可以用：

```text
snd_<sound_resource_id>_bank<sound_bank>_ogg_<ogg_chunk_index>.ogg
```

示例：

```text
snd_00067_bank01_ogg_00001.ogg
```

视频内嵌音频判断：

- 全部 7801 个 CRID 视频 slice 中，456 个包含 `@SFA` 音频块
- `main`：230 个包含内嵌音频，4972 个不包含
- `patch`：226 个包含内嵌音频，2373 个不包含
- `ac0902_608..627` 样本没有 `@SFA`，所以导出 MP4 没有音轨是符合原始数据的
- `main:97` 样本包含 `@SFA`，导出后 `ffprobe` 显示 `h264 + alac`，说明内嵌音频解复用流程可工作

当前需要分清两类音频：

- CRID 内嵌 `@SFA`：可以随视频一起封装进 MP4
- 外部 OGG/PCM：需要从游戏事件、sound id 或 native 调度逻辑中建立对应关系，不能直接按视频文件名自动匹配

## 当前可用标准

项目已经达到“可继续批处理前的审计可用标准”：

- 能生成可复现清单
- 能区分唯一命名、多候选、无候选视频
- 能解析音频 ID 映射
- 能将图像按 `acXXXX` 做初步分类
- 会默认 dry-run，降低误操作风险

尚未达到“全自动最终整理标准”：

- 视频拼合仍需共享 chunk 复核
- z2d 真实图像格式仍需专门解码器或格式解析
- 音频和视频是否存在独立同步表尚未完全确认

## RAMDISK 全量导出复核

已使用 48GB RAMDISK 完成全量导出，并备份到：

```text
D:\MagiaRe_RAMDISK_Backup_20260603_032042
```

导出结果：

| 类型 | 数量 | 状态 |
| --- | ---: | --- |
| MP4 | 7801 | `ffprobe` 失败 0 |
| 含内嵌音轨 MP4 | 456 | 与 CRID `@SFA` 扫描一致 |
| 无内嵌音轨 MP4 | 7345 | 需要外部 OGG/PCM 关联审计 |
| OGG | 9952 | `ffprobe` 失败 0 |
| PCMRAW | 21 | 0 字节文件 0 |
| Z2D raw | 12083 | 0 字节文件 0 |

新增 `video-review` 命令后，已生成：

- `asset_manifests/video_review_sequences.csv`
- `asset_manifests/video_review_items.csv`
- `asset_manifests/video_review_unique_runs.csv`
- `asset_manifests/video_review_summary.md`
- `asset_manifests/video_review_concat_plans/`

复核结论：

- 263 个视频序列候选中，261 个仍涉及共享 chunk，不能直接最终合并
- 2 个序列存在同名映射歧义：`ac3409_263`, `ac8052_001`
- `ac0902` 后半段存在 26 个唯一连续片段，可用于视觉预览
- 已在 D 盘备份目录生成 26 个 `ac0902` 预览拼合 MP4，全部可被 `ffprobe` 读取，失败 0，均无音轨
