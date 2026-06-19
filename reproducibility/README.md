# Reproducible analysis inputs

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

参考布局见 `input-layout.json`。本机已验证输入的指纹见
`reference-inputs.sha256.csv`。校验：

```powershell
powershell -ExecutionPolicy Bypass -File reproducibility/scripts/Test-ReferenceInputs.ps1 `
  -InstalledPullRoot A:\magireco_installed_pull_20260603 `
  -UnpackedProjectRoot C:\path\to\magireco-slot-asset-pipeline-working-copy
```

OBB 可由仓库根目录的 `magireco_slot_auto_downloader.py` 从游戏资源端点下载并通过
`jobb.jar` 解包。该脚本不获取 APK；APK 和 split APK 必须从协作者自己的合法安装导出。

## 派生证据包

```powershell
powershell -ExecutionPolicy Bypass -File reproducibility/scripts/New-AnalysisEvidenceBundle.ps1 `
  -AssetManifestRoot C:\path\to\working-copy\asset_manifests `
  -ResearchRoot A:\magireco_corrected_research_20260612 `
  -BiliRoot A:\magireco_bili_fulltest_20260603 `
  -AdditionalEvidenceRoot A:\another_runtime_capture_root `
  -OutDir D:\MagiReco_Reverse\release_assets
```

脚本只收集 `.csv/.json/.md/.txt/.srt` 派生证据，生成逐文件 SHA-256 清单和 ZIP，
不会收集媒体、APK、OBB、native 库或原始二进制资源。

已发布证据包及其 GitHub 返回的摘要见 `releases/analysis-evidence-v18-20260619.json`。
