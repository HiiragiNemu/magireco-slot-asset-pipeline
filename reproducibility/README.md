# Reproducible analysis inputs

> 2026-10-03 文档校准：当前项目入口见 [仓库首页](../README.md) 与
> [PROJECT_STATUS](../docs/PROJECT_STATUS.md)。本页的输入指纹和 v18 打包器保留历史复现用途，
> 不代表现代审查库存已全部打包。当前输入和产物使用 D: 耐久路径，不再依赖 A: RAMDISK。

本目录定义从原始安装输入到本仓库派生清单的可复现边界。目标是让协作者无需猜测
目录布局、版本或工具链，同时不在 GitHub 再分发第三方 APK、OBB、native 库和游戏媒体。

## 仓库与 Release 的内容边界

仓库保存：

- 分析、运行时探针、渲染、QA 和集合构建代码；
- composition plans、排除规则、字幕修正规则；
- 参考版本的文件名、大小和 SHA-256；
- 外部工具版本与获取地址；
- 生成派生分析证据 Release 的 PowerShell 脚本。

派生证据 Release 可以保存：

- CSV/JSON/Markdown 资产清单；
- production manifests；
- 官方运行时解析后的事件 JSON/CSV；
- GDB/Z2D/DGM/CRI 名称映射和事件时间轴。

不上传：APK、split APK、OBB、`libGameProc.so`、JADX 反编译源码、原始二进制表、
SMZ/OGG/PCM、DGM/CRI/MP4、游戏截图或包含游戏资源的整盘归档。它们是第三方专有输入，
应由合法持有者从自己的安装或仍可访问的官方资源端点取得。

## 本地布局

参考文件组见 [input-layout.json](input-layout.json)。其中旧 A:／C: 路径仅是历史示例，
不应照搬。参考版本的输入指纹见 [reference-inputs.sha256.csv](reference-inputs.sha256.csv)。
先确认持有对应版本；该命令会读取所列原始文件计算哈希，仅在需要验证输入时执行，
不作为每轮工作或目录清理的默认步骤：

```powershell
powershell -ExecutionPolicy Bypass -File reproducibility/scripts/Test-ReferenceInputs.ps1 `
  -InstalledPullRoot D:\magia\MyProducts\casino\magireco_installed_pull_20260603 `
  -UnpackedProjectRoot D:\magia\MyProducts\casino\com.universal777.magireco-Ga9DaxEd9F9Lqn9OVKVSfw==
```

OBB 可由仓库根目录的 `magireco_slot_auto_downloader.py` 从游戏资源端点下载并通过
`jobb.jar` 解包。该脚本不获取 APK；APK 和 split APK 必须从协作者自己的合法安装导出。

## 项目交接目录

`project-kit/` 是当前分支的交接索引：它列出需要 Git 跟踪的非 Python 探针/配置/清单、
巨大输入文件的 fingerprint-only 处理策略，以及公开 Release 允许携带的派生证据边界。
新增破解分析或资源合并依赖时，先判断它是否是小型可审计文本资产；若是，提交到 Git，
若是第三方 payload 或巨大媒体/二进制，只记录哈希、来源和重建方式。

## 历史 v18 派生证据包（按需，不自动执行）

以下脚本按旧 v18 目录合同收集资料，不能据此宣称已覆盖现代全部 production roots。
仅在明确需要交付相应历史证据包时使用；日常提交或清理不重复制作 ZIP／整目录副本。
路径变量须填入该次交付明确引用的现有 D: 目录，并先确保输出目录存在：

```powershell
$AssetManifestRoot = 'D:\magia\MyProducts\casino\com.universal777.magireco-Ga9DaxEd9F9Lqn9OVKVSfw==\asset_manifests'
$ResearchRoot = 'D:\magia\MyProducts\casino\magireco_corrected_research_20260612'
$BiliRoot = 'D:\path\to\the\referenced-historical-bili-root'
$EvidenceRoot = 'D:\path\to\the\referenced-runtime-evidence'
$OutDir = 'D:\path\to\an\existing-output-directory'
powershell -ExecutionPolicy Bypass -File reproducibility/scripts/New-AnalysisEvidenceBundle.ps1 `
  -AssetManifestRoot $AssetManifestRoot `
  -ResearchRoot $ResearchRoot `
  -BiliRoot $BiliRoot `
  -AdditionalEvidenceRoot $EvidenceRoot `
  -OutDir $OutDir
```

脚本只收集 `.csv/.json/.md/.txt/.srt` 派生证据，生成逐文件 SHA-256 清单和 ZIP，
不会收集媒体、APK、OBB、native 库或原始二进制资源。

历史已发布证据包及其 GitHub 返回的摘要见 [releases/](releases/)。例如
`analysis-evidence-v18.27-20260628` 纳入了当时的 runtime evidence package QA、
promotion/isolation queue 和带 package gates 的 pipeline strategy report；仍只包含
`.csv/.json/.md/.txt/.srt` 派生证据，不包含 `.jsonl` 原始 Frida 捕获、WAV、截图、
视频或任何游戏 payload。
