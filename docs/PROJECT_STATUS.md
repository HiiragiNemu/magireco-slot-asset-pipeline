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

新增 `sound-request-audit` 后，已解析 `zg_snd_request_tbl.bin`：

| 项目 | 数量 |
| --- | ---: |
| 声音表可用字符串 | 22232 |
| 声音请求行 | 11249 |
| 可连接到 `sound_id.dat` 的请求行 | 9934 |
| 带描述标签的请求行 | 8501 |
| 附近存在 `.smz/.pcm` 媒体候选的请求行 | 11203 |

重要限制：

- 声音请求表内有大量语义标签，如 `seq_共通_発展`、`結果表示_WIN`、`セリフ` 等，可用于音频分类和人工复核。
- 当前未发现 `ac0902` 这类视频编号直接出现在声音请求表中。
- `nearest_media` 只是同表邻近候选，不能直接当作视频同步关系。
- 视频和外部 OGG/PCM 的最终同步关系仍需继续审计演出调度、事件表或 native 逻辑。

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
- MP4 容器审计未发现“只有音频、没有视频流”的文件；7801 个 MP4 均有视频流
- 456 个含内嵌音频的 MP4 中，三帧采样发现 2 个全黑画面片段、2 个近黑画面片段，这可能解释“像只有声音没有画面”的观察
- `ac0902_*` 唯一命名视频共 483 个，全部无内嵌音轨；预览拼合后仍无音轨是符合原始 CRID 数据的

## RAMDISK B 站全量测试

已重新输出全量 MP4 到：

```text
A:\magireco_bili_fulltest_20260603\videos
```

本轮没有启用未验证的序列合并，也没有把外部 OGG/PCM 强行混入视频。输出策略是：

- CRID 内嵌 `@SFA` 音频：随视频封装进 MP4
- 无内嵌 `@SFA` 的视频：保持无声
- 外部 OGG/PCM：仅保留声音请求与标签候选，等待后续调度关系审计

结果：

| 项目 | 数量 |
| --- | ---: |
| 输出 MP4 | 7801 |
| 输出体积 | 3572329040 字节 |
| 有视频无音轨 | 7345 |
| 有视频有音轨 | 456 |
| 纯音频/无视频 MP4 | 0 |
| 全黑采样视频 | 133 |
| 近黑采样视频 | 259 |

特殊复核目录：

```text
A:\magireco_bili_fulltest_20260603\review_special
```

其中：

- `audio_only`：0 个文件
- `blackish_video`：133 个文件
- `mostly_black_video`：259 个文件

B 站元数据候选已生成：

```text
asset_manifests/bilibili_metadata_summary.md
asset_manifests/bilibili_video_metadata_candidates.csv
asset_manifests/bilibili_sound_label_candidates.csv
```

当前可获取的投稿辅助信息包括：

- 应用正式名：`スマスロ マギアレコード 魔法少女まどか☆マギカ外伝`
- APK 版本：`versionName 1.0.0`, `versionCode 31`
- 263 个视频序列候选的时长、分辨率、音轨数量、共享 chunk 状态
- 2480 条可读声音请求标签候选
- `ac` 图像分组和示例素材名，可辅助判断故事、角色、结尾、简介、UI 场景

## 2026-06-04 增量审计

### review_special 关系确认

`review_special` 目录是复核索引，不是原视频的唯一位置。当前在 NTFS 上优先使用 hardlink：

- `review_special\blackish_video\main_video_1150.mp4` 与 `videos\Unclassified_Slices\main_video_1150.mp4` 是同一文件数据的 hardlink
- `review_special\blackish_video\main_video_0529_candidates2.mp4` 与 `videos\MultiCandidate_Slices\main_video_0529_candidates2.mp4` 是同一文件数据的 hardlink

结论：

- 没有移动原视频
- `review_special` 中的文件仍在 `videos` 分类目录中可见
- `blackish_video` / `mostly_black_video` 只是亮度采样复核列表，不是删除列表；里面包含不少合法暗色素材、卡面、边框或 UI 片段

### 音频位置确认

当前 A 盘测试结果中：

- 带内嵌音频 MP4：`A:\magireco_bili_fulltest_20260603\review_audio\with_embedded_audio`
- 外部 OGG：`A:\magireco_bili_fulltest_20260603\audio_assets\audio\ogg_raw`
- 外部 PCM：`A:\magireco_bili_fulltest_20260603\audio_assets\audio\pcm_raw`

内嵌音频统计：

| 项目 | 数量 |
| --- | ---: |
| 有视频无音轨 MP4 | 7345 |
| 有视频有音轨 MP4 | 456 |
| `MultiCandidate_Slices` 中有音轨 | 49 |
| `Unclassified_Slices` 中有音轨 | 407 |
| `ac0902_演出` 中有音轨 | 0 |

456 个内嵌音频 MP4 的音频编码是 `alac`。外部 OGG/PCM 已导出并按 `sound_id.dat` 命名，但尚未找到可证明同步到具体视频片段的调度关系。

### 候选数连续段合并测试

新增命令：

```powershell
python magireco_asset_pipeline.py merge-candidate-runs --video-dir A:\magireco_bili_fulltest_20260603\videos --out-dir A:\magireco_bili_fulltest_20260603\merge_tests\candidate_runs_command_execute_hflip_video_only --execute --hflip --drop-audio --probe
```

规则：

- 只处理 `MultiCandidate_Slices`
- 文件名需匹配 `main_video_NNNN_candidatesX.mp4` 或 `patch_video_NNNN_candidatesX.mp4`
- 按 `package + index` 排序
- 仅当 index 连续且 `candidatesX` 相同时合并
- 单片仍输出一份，便于形成完整复核目录
- 本次执行使用 `--hflip --drop-audio`，因此输出为水平翻转校正后的 video-only 测试结果

结果：

| 项目 | 数量 |
| --- | ---: |
| 原 `MultiCandidate_Slices` MP4 | 607 |
| 输出 MP4 | 73 |
| 真正合并段 | 29 |
| 单片保留 | 44 |
| 执行失败 | 0 |

示例：

```text
main_video_0071-0099_candidates24.mp4
```

该文件来自 29 个源片段，时长 48.100 秒，源片段中 3 个带内嵌音频；当前测试输出故意去掉音频，避免混合“有音轨/无音轨”片段时产生错误合并。

### 镜像方向问题

用户复核确认当前导出视频存在左右镜像问题。本轮生成了方向样张：

```text
A:\magireco_bili_fulltest_20260603\orientation_check
```

候选数合并测试输出已使用 `hflip` 做水平翻转校正。原 `videos` 全量目录未被改写。

### 安装态拉取与完整性

通过 MuMu / adb root 拉取安装态内容到：

```text
A:\magireco_installed_pull_20260603
```

拉取结果：

| 目录 | 文件数 | 字节 |
| --- | ---: | ---: |
| `data_app_package` | 11 | 832841272 |
| `data_user_0` | 16 | 154288355 |
| `sdcard_Android_data` | 5 | 6158460910 |
| `sdcard_Android_obb` | 0 | 0 |

完整性判断：

- 安装态 6 个 APK/split APK 与项目目录本地 APK/split APK 的 SHA256 全部一致
- 安装态 `main.9...obb` 与 `patch.9...obb` 与本地 `downloaded_assets` 版本 SHA256 一致
- 因此现有 APK/JADX/apktool 输入和 Python 复刻下载得到的 OBB 主资源没有发现缺失或偏差

新增有价值内容：

```text
A:\magireco_installed_pull_20260603\data_user_0\files\assetpacks\OnDemandPack01\31\31\assets\smz.bin
A:\magireco_installed_pull_20260603\data_user_0\files\assetpacks\OnDemandPack01\31\31\assets\smz_add.bin
```

`smz_add.bin` 是 `smz.bin` 的 32-bit 小端偏移表，共 9753 个偏移，定义 9752 个资源块。当前未识别为 OGG/PNG/JPEG/MP4，也不能直接用 zlib/bz2/lzma 解压；它更可能是额外图像、贴图或模型相关资源容器，后续需要单独格式研究。

### D 盘归档

本轮新增内容已复制到：

```text
D:\MagiaRe_RAMDISK_Delta_20260604_002343
```

归档内容包括：

- 候选数合并测试输出与 manifest
- 方向样张
- 带内嵌音频 MP4 复核集合
- `review_special` 复核目录
- `OnDemandPack01` 和小型运行态文件

没有重复归档全量 MP4、raw OGG/PCM、APK、OBB；这些已在旧 D 盘备份或本地工程中存在，且哈希/数量/总大小已验证一致。
