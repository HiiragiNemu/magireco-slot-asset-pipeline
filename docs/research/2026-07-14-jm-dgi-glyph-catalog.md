# JM DGI 字形目录与 ASTC 导出

## 结论边界

故事画面实际引用的位图字形是 `dgi.bin` 中的
`JM_<Unicode>_<family>_<variant>` 资源。`utf8_font_package.bin`、
`sjis_font_package.bin`、`hankaku.dgi` 与 `zenkaku_*.dgi` 属于另一条
DEBUG PRINT 路径；当前 APK、split 和已安装资源中不存在这些文件，不能再把它们
写成故事字幕字体来源。

已验证的 DGI 静态关系是：

- `libGameProc.so` 文件偏移 `0x1461600` 是 5785 项相对名称表；
- `dgi_add.bin` 提供对应的有序 chunk 边界；
- 其中 4124 项是 JM 字形，覆盖 1056 个独立 Unicode 码点；
- JM DMP payload 的格式码 `0x001D` 对应 ASTC 4x4；
- DMP 头只有纹理固有宽高，没有 advance、bearing、baseline、anchor 或图层
  transform，排版参数必须继续从 Z2D 或运行时证明。

## 只读工具

`tools/frida_runtime_probe/extract_jm_dgi_glyph_catalog.py` 默认执行完整审计但不写
文件。源归档始终以只读方式打开：

```powershell
python tools/frida_runtime_probe/extract_jm_dgi_glyph_catalog.py `
  --native-lib D:\path\unpacked_lib\lib\arm64-v8a\libGameProc.so `
  --dgi-bin D:\path\unpacked_assets\assets\dgi.bin `
  --dgi-add D:\path\unpacked_assets\assets\dgi_add.bin
```

只有显式提供输出参数时才会生成新文件：

```powershell
python tools/frida_runtime_probe/extract_jm_dgi_glyph_catalog.py `
  --native-lib D:\path\unpacked_lib\lib\arm64-v8a\libGameProc.so `
  --dgi-bin D:\path\unpacked_assets\assets\dgi.bin `
  --dgi-add D:\path\unpacked_assets\assets\dgi_add.bin `
  --json-out D:\audit\jm_dgi_catalog.json `
  --csv-out D:\audit\jm_dgi_catalog.csv
```

JSON/CSV 每个字形记录 archive index、名称、码点、family、variant、offset、
chunk size、chunk/payload SHA256、完整 DMP 字段、ASTC 参数，并固定记录
`typography_metrics_present: false`。JSON 还默认记录三个源文件的 SHA256；只在临时
快速检查时可用 `--skip-source-hashes` 跳过整文件 hash。

ASTC 导出是显式操作。建议先用精确名称做小批量：

```powershell
python tools/frida_runtime_probe/extract_jm_dgi_glyph_catalog.py `
  --native-lib D:\path\libGameProc.so `
  --dgi-bin D:\path\dgi.bin `
  --dgi-add D:\path\dgi_add.bin `
  --astc-dir D:\audit\astc_sample `
  --astc-name JM_74B0_00009N7X_MR060 `
  --astc-name JM_74B0_0000GAMW_MR010
```

输出只是标准 `.astc` 容器，不会自动解码或 upscale。后续如调用 `astcenc`，其
版本、可执行文件 hash、命令行和 PNG hash 都应进入下一层审计 manifest。

## 中文字幕覆盖门禁

用 `--coverage-text` 或 UTF-8 `--coverage-file` 提交待验证文本。默认忽略空白，
但不忽略其他任何字符；出现一个缺失码点就返回退出码 `3`：

```powershell
python tools/frida_runtime_probe/extract_jm_dgi_glyph_catalog.py `
  --native-lib D:\path\libGameProc.so `
  --dgi-bin D:\path\dgi.bin `
  --dgi-add D:\path\dgi_add.bin `
  --coverage-file D:\audit\translated_dialogue.txt `
  --json-out D:\audit\translated_dialogue_coverage.json
```

当前 JM 集合足以覆盖游戏已有日文语料，但不是完整日文字库，更不是完整简中文字
库。中文字幕缺字必须明确记录并采用另行审计的 fallback；不得把 fallback 字体称为
游戏原生字形。

## 测试

纯离线合成向量始终运行。三个已安装资源向量通过环境变量显式启用：

```powershell
$env:MAGIRECO_SLOT_ASSET_ROOT = 'D:\path\com.universal777.magireco-...'
python -m unittest test_extract_jm_dgi_glyph_catalog.py -v
```

安装资源测试校验 archive index 953、4004、4006 的名称、offset、尺寸以及
chunk/payload SHA256，同时校验 4124 个字形和 1056 个独立码点的全量闭合计数。
