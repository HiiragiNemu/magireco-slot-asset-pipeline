# 可复现的中文字幕字体依赖

本目录把中文字幕字体从“这台电脑正好装了什么字体”变成固定上游版本、固定文件和
固定哈希的依赖。Git 只保存清单、覆盖集合和草案配置；17.8 MB 字体二进制及其许可
文本下载到已忽略的 `reproducibility/local_inputs/fonts/`，不会进入仓库提交。

## 固定依赖

- 字体：`NotoSansSC-VF.ttf`（family `Noto Sans SC`，face 0）
- 上游：[notofonts/noto-cjk](https://github.com/notofonts/noto-cjk)
- 版本：Noto Sans CJK 2.004，tag `Sans2.004`
- 固定 commit：`523d033d6cb47f4a80c58a35753646f5c3608a78`
- 固定字体 URL：
  `https://raw.githubusercontent.com/notofonts/noto-cjk/523d033d6cb47f4a80c58a35753646f5c3608a78/Sans/Variable/TTF/Subset/NotoSansSC-VF.ttf`
- 字体大小：17,773,132 bytes
- 字体 SHA-256：
  `D68BAFCB48A2707749396AA12BBBD833CB70401F3A9A689FD2902C7E0D295964`
- 许可证：SIL Open Font License 1.1 (`OFL-1.1`)
- 固定许可证 URL：
  `https://raw.githubusercontent.com/notofonts/noto-cjk/523d033d6cb47f4a80c58a35753646f5c3608a78/LICENSE`
- 许可证大小：4,301 bytes
- 许可证 SHA-256：
  `6A73F9541C2DE74158C0E7CF6B0A58EF774F5A780BF191F2D7EC9CC53EFE2BF2`

该字体是明确标注的 `audited_chinese_fallback`，不是游戏原生字体。Windows 当前安装的
`C:\Windows\Fonts\NotoSansSC-VF.ttf` 是另一个 non-release build（本机 SHA-256
`763146584CF0710223441356B4395E279021B0806C196614377A7A0174AE074A`），不得静默代替
上述锁定文件。

## 获取一次，随后离线校验

联网取得并校验字体与许可证：

```powershell
python reproducibility/scripts/fetch_font_dependencies.py
```

缓存已复制到另一台机器后，以严格离线模式确认；该命令不会发起网络请求：

```powershell
python reproducibility/scripts/fetch_font_dependencies.py --offline
```

缺文件、大小不符或 SHA-256 不符都会失败。脚本默认也不会覆盖损坏缓存；只有显式
`--repair` 才会重新下载到临时文件，校验通过后再原子替换。

如需把缓存放到 Git 工作区之外，可指定 `--cache-dir`；随后应复制或链接锁定字体到
草案配置所引用的默认相对路径，或生成一份只修改 `path` 的本机配置，不能修改 SHA。

## ac7114/15/16 当前门禁

`ac7114_16.zh-candidate-coverage.json` 固定了审阅单中的 10 条候选文本和 34 个唯一可见
码点。锁定的 Noto 字体完整覆盖 34/34。`ac7114_16.zh-font-config.draft.json` 可直接交给
现有 `load_font_config` / `validate_font_binding` 做真实文件、family、SHA 和 cmap 覆盖
校验。

这只关闭“中文缺字与隐式系统 fallback”问题。以下状态保持不变：

- 中文候选仍是 `NOT_HUMAN_APPROVED`；
- 草案仍是 `release_eligible=false`；
- 日文游戏字体绑定、游戏布局/字号/描边/安全区证据仍需独立完成；
- 在翻译与布局获批前，六版 renderer 会继续 fail closed。
