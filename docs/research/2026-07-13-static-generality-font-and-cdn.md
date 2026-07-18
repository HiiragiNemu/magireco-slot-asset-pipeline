# 2026-07-13 静态通用性、游戏字体与 CDN 审计

本报告把三个容易混淆的问题分开回答：当前外部解释器到底通用到哪一层；正式
日文/中文字幕应使用什么字体；能否仿照另一个游戏从 Slot 服务器取得高清母版。
它是只读审计，不晋升任何视频，也没有修改或枚举服务器对象。

## 1. 目前通用的是资源和路由骨架，不是全部 AV 语义

已经能够外部、可复现地解释的层：

- `kind,row,selector -> DirInfoTable -> EventInfo -> event code`。解码器位于
  [`decode_dirinfo_event_tables.py`](../../tools/frida_runtime_probe/decode_dirinfo_event_tables.py)，
  当前原生表含 290 个 DirInfo entry、9,732 个 EventInfo；926 个 production event
  code 覆盖 3,908 条 route row。
- `GDB -> Z2D -> DGM -> CRI` 资源身份链。生产代码在
  [`magireco_asset_pipeline.py`](../../magireco_asset_pipeline.py)，不按 `ac` 后缀数字
  猜 CRI index。
- `sound code -> request_id -> ReqData/marker/SMZ` 结构，以及
  `sound_resource_id -> OGG chunk` 静态连接。
- SP Story 的五张 kind lottery 表。该机制对 SP Story family 通用，不代表其他玩法
  使用同一 selector 或 lottery 表。
- Direction 的 frame update、table/macro dispatch 和 SE/BGM/FADE/EVENT queue
  骨架已经定位。

仍不能称为“全静态、全非黑盒”的层：

- 当前 DGM interval 在名称后 72 bytes 内按媒体帧数匹配 u16 pair，parent 在 32
  bytes 邻域内关联；二者都有证据 offset，却仍是有界启发式，不是完整 Z2D 语法。
- 外部 compositor 尚未完整实现 DGI image layer、shader、nameplate。
- 所有玩法的上游状态到完整 Direction sequence 尚无统一解释器。
- PLAY/STOP 因果、继承的 outer BGM、ZG play-info 与 CSL transport 身份等价尚需
  同一次自然运行闭合。
- LP、影片结束、尾帧 hold 和 voice tail 的 renderer 状态规则尚未形式化。
- 全事件角色语音与图形字幕尚不能自动得到唯一、完整、逐帧关联。
- 剧情层、素材层、老虎机特效层的“给观众看什么”是产品语义，不能只从容器结构
  自动推出。

所以当前正确表述是：**资源身份、事件路由和调度骨架具有通用机制；最终 AV 时间、
继承声音和观众语义尚未完全通用。** 动态捕获的目标是验证并补全解释器，而不是按
视觉逐个猜 926 个事件。完整解释器建成后，动态调试应降为跨玩法抽样一致性测试。

## 2. 字体结论：Yu Gothic 只是临时默认值

仓库中的 `Yu Gothic` 只出现在渲染脚本默认参数，例如
[`render_event_manifest.py`](../../tools/frida_runtime_probe/render_event_manifest.py) 和
[`render_subtitle_editions.py`](../../tools/frida_runtime_probe/render_subtitle_editions.py)。
提交历史没有给出 APK、运行时或官方字体来源，因此不得把它称作游戏字体。

只读检查 base APK、ABI/密度/语言 split 和 InstallTimePack 后：

- 没有发现 TTF、OTF、TTC、FNT、WOFF 或独立 font 目录；
- `split_config.zh.apk` 只有 Android 资源与签名条目，不携带中文字形；
- 日文 split 同样没有独立字体。

早期字符串命中需要更正：`utf8_font_package.bin`、`sjis_font_package.bin`、
`hankaku.dgi` 和 `zenkaku_*.dgi` 属于缺失的 debug-print 路径，不是当前故事字库。
`LoadDebugFontUtf8@0x42ff3f0` 恒返回 false，`DrawPrintUtf8Text@0x42ff4fc` 直接返回；
SJIS loader `0x43172c4` 虽包含旧加载逻辑，但这些文件在 APK、split、installed pull
和解包资源中均不存在。

真实故事文字链是：

1. `CZ2DString::SetString` 使用 DGI archive 内
   `JM_<Unicode>_<family>_<variant>` glyph 与 Z2D authored placement。自然日志先
   设置逐字 JM 引用，再设置完整日文台词；同次未见 `FontImpl::drawText*`。
2. `libAMAIN` 的 `CDrawRes::SetFont` 调用 Java
   `DrawMng.FontBmpCreate`。Java 代码用未设置 Typeface 的 Android `Paint` 与
   `Canvas.drawText` 逐字生成 bitmap atlas；这是系统默认字体路径，但尚未证明故事
   字幕使用它。

`zg::sprite::Renderer::Config::setFontFilePath`/`FontImpl` 也存在，但默认 font path
为空，现有运行日志只证明 hook 安装，没有故事字幕 draw 调用，不能据此选字体。

可复核的本地证据包括：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260619_round2\raw\ac0911_001__runtime.jsonl
line 46: CZ2DString::SetString("環さんはこんな話聞いたことある？")

unpacked_assets\assets\dgi.bin
SHA-256 4D5FD52F6DD61D33B5A0EC6576BC9841089AE8B91BCAB262C0E9B3E1E17F487E
unpacked_assets\assets\gdb.bin
SHA-256 641C1B98353BF01365394F25E8B038A22B5F479AED0B536C88CC79AA0C9349D1
unpacked_assets\assets\z2d.bin
SHA-256 146BC4016362A3924FFF921DCF4662F282368A9FD8DD554C2343B4F67031E94C
```

当前 `render_event_manifest.py` 写出的 render manifest 也没有记录实际 fontconfig/
libass 解析到的字体文件、字库 hash 或 fallback。即使画面看起来接近，现有输出也不
满足“游戏字体可审计复刻”的证据要求。

JM DGI 静态目录已经闭合：原生相对名表在 `libGameProc.so` 文件偏移 `0x1461600`，
含 5,785 个名称；`dgi_add.bin` 有 5,786 个单调 LE u32 边界且末值等于 `dgi.bin`
大小，所以每个名称和 chunk 精确一一对应。4,124 个 JM glyph 覆盖 1,056 个码点：
`0000GAMW` 族 2,833 个 52x52，`00009N7X` 族 1,291 个 56x56。DMP header 为
`<4sIIIHHIIHH>`，format `0x1d` 对应 ASTC 4x4；header 不含 typography metrics。

全量 Z2D 有 49,308 次 JM 引用、4,120 个独立文件名、零 dangling；现有 2,031 条
独立 display text 的 1,053 个非空格码点全部有 glyph。该集合只覆盖约 15.13% 的
Shift-JIS 双字节 repertoire 和约 8.46% 的 GB2312 CJK，因此它是语料专用字库，
不是任意 CJK 字体。

正式三版必须增加以下 fail-closed 门禁：

- 导出 JM DGI catalog、ASTC payload、码点、family/variant 与逐 chunk hash；
- 解出 Z2D image transform、layer、anchor 和间距，不能把 52/56 纹理尺寸当 metrics；
- 从游戏帧裁取日文文字，与 JM bitmap 和 Android atlas 做像素对照；
- production manifest 记录 `font_source/font_hash/layout_profile/glyph_coverage`；
- 对全部中文字幕码点运行 coverage 检查；
- 中文任一缺字时阻断，不能静默回退到 Yu Gothic；
- 若官方日文字形确实不覆盖中文，需要明确选择“复现游戏排版、使用可审计中文
  fallback”的规范，不能宣称中文也使用不存在的官方字形。

## 3. Slot CDN 与 Exedra 路线不是同一种机制

`D:\magia\videodownloader.py` 的 SHA-256 为
`5B4B39D2B1D7EAC63933A742FE42BE3608AC1C668F8A519B70D901CB9F24FBDD`。它属于
Magia Exedra，只能作为“从客户端代码追溯真实资源入口”的方法参考。其 token、
AES、master manifest、m3u8 和 `Movie/...` 路径没有 Slot 证据，不能复制到本项目，
也没有把该脚本或其中配置上传仓库。

Slot Android 客户端使用固定资源根：

```text
http://app.universal-777-res.com/magireco/
main.<resource-version>.com.universal777.magireco.obb_NNNN.obb.jar
patch.<resource-version>.com.universal777.magireco.obb_NNNN.obb.jar
```

静态依据位于客户端 `ResourceCheck.java`、`ResourceDownload.java`、
`MyDownloaderService.java` 和 `ResCRC.java`：客户端先 HEAD，再以 GET/Range 下载
上述对象，没有 token、manifest API 或 playlist。`latestVerCode=9` 是 OBB 资源
revision，不是 APK versionCode；当前 APK 是 versionCode 31 / versionName 1.0.0。

当前 Android revision 9 的客户端可见分发集合已经闭合：

| 部分 | 对象数 | 声明总大小 |
| --- | ---: | ---: |
| main OBB chunks | 217 | 3,411,813,224 B |
| patch OBB chunks | 175 | 2,746,538,910 B |

历史流量恰好有 392 次 HEAD 和 392 次 GET，即每个声明对象各一次。合并 OBB 与安装
导出在尺寸和 SHA-256 上一致。唯一声明的 `OnDemandPack01` 只有
`smz.bin/smz_add.bin`；InstallTimePack 才包含 DGI/GDB/OGG/PCM/Z2D。APK、两个 OBB
和 OnDemand SMZ 合计约 7.143 GB（十进制），与商店所述首启最大约 7.5 GB 相符。

声音资产存在不等于当前账号已解锁。官方
[应用发布公告](https://www.universal-777.co.jp/news/20260415002485/) 与
[Google Play](https://play.google.com/store/apps/details?id=com.universal777.magireco)
明确说明另售 Sound Pack 会解锁主要通常时 BGM 和 bonus music。OnDemand SMZ 已
安装只证明客户端能取得数据，不能证明 entitlement、音量设置或 native gate 当前为
启用。因此外层 BGM 审计必须把购买/设置状态作为运行时 provenance；无声捕获不能
直接晋升为“游戏原生没有 BGM”。

2026-07-14 已进一步只读证明当前实例七项 addon saved/active 全为 0，并定位索引 6
控制的 222-ID `SoundMng` 静音表；通用 play/channel 路径均经过该门禁，普通游戏/
Android 音量则没有静音。完整函数地址、表连接和 ac7114/15/16 结论边界见
[`2026-07-14-sound-pack-entitlement-gate.md`](2026-07-14-sound-pack-entitlement-gate.md)。

2026-07-13 仅对清单内三个已知 URL 做精确 HEAD，没有枚举路径：

| 对象 | HTTP | Content-Length |
| --- | ---: | ---: |
| main_0001 | 200 | 15,728,640 B |
| main_0217 | 200 | 14,426,984 B |
| patch_0175 | 200 | 9,755,550 B |

这些结果说明端点仍在线。代码还列出可选名 `cri3.bin/cri3_add.bin`，但当前安装、
ResCRC、URL 清单和唯一 PAD pack 中都没有实体；它只能记为通用或遗留槽位，不能当作
缺失高清包。

客户端代码、流量、对象清单和 7,801 个已抽取视频的 probe inventory 中都没有发现：

- m3u8/HLS playlist；
- quality/720p/1080p 档位或选择逻辑；
- 同一故事资源的高分辨率变体；
- 独立高清对象路径。

现有 inventory 的最大画布是 512x416；故事主画面常为 416x232，其他 512x416 或
512x288 项通常是不同屏幕/图层，不能冒充同一故事的高清版本。

公开页面复核范围：

- [Universal 官方产品页](https://www.universal-777.com/product/slot/magireco/)
- [官方数字指南](https://www.universal-777.com/product/digitalguide/ps/magireco/)
- [官方应用发布公告](https://www.universal-777.co.jp/news/20260415002485/)
- [Google Play](https://play.google.com/store/apps/details?id=com.universal777.magireco)
- [Apple lookup](https://itunes.apple.com/lookup?id=6752765295&country=jp)

产品页、数字指南和公告源码只见静态图片、商店链接与官方频道入口，没有发现
`.mp4/.m3u8/.webm` 或 playlist。iOS 是独立包，合法取得安装/初启流量后可做有限
平台对照，但目前没有证据表明 iOS 动画分辨率更高。

## 4. 可执行判断

CDN 路线保留，但当前只应执行可由客户端证据导出的有限检查：历史 resource revision、
合法平台包对照、明确的 catalog/质量字段和官网公开宣传源。不得盲扫 CDN，也不得把
官网宣传片冒充游戏运行时原生媒体。

截至本报告日期，没有证据支持从 Android Slot CDN 下载比现有 CRI/USM 更高分辨率的
动画。这个结论不证明发行方内部不存在未公开母版，也不证明 iOS 分发完全相同；它只
限定当前 Android 客户端可见集合。主线继续是 Slot 自身的静态解释器、自然运行证据和
外部 AV 复刻，绝不因 Exedra 对照样本而放弃。

## 2026-07-16 CDN 与公开页面复核

只对客户端明确声明、此前已下载的三个 revision-9 边界对象重新执行 HEAD；没有枚举
未知路径。三者仍为 HTTP 200、支持 byte range，大小与 2026-07-13 完全一致：

| 对象 | Content-Length | Last-Modified | ETag |
| --- | ---: | --- | --- |
| `main..._0001.obb.jar` | 15,728,640 | 2026-02-13 01:27:24 GMT | `33cdfaa5096a5a9966104171c29416a8` |
| `main..._0217.obb.jar` | 14,426,984 | 2026-02-13 01:30:29 GMT | `bc848027033696ea5fcb7b727002508f` |
| `patch..._0175.obb.jar` | 9,755,550 | 2026-02-13 01:33:10 GMT | `8db472602cb0b8fe940854f4d2f93029` |

Google Play 当前说明仍是首启下载约 7.5 GB 资源，并只列六类 addon 功能；官方发布
公告只描述模拟器便利功能与 Sound Pack，没有高清、quality tier、独立动画下载或
视频播放列表。公开公告源码也没有 `.mp4/.m3u8/.webm` 入口。结合客户端固定
`main/patch revision 9`、392 对象闭合、安装态 hash 对齐和 7,801 个视频 probe，结论
保持不变：**当前可验证的 Android Slot CDN 是现有 OBB 分片源，不是隐藏的高清动画
CDN。**

因此 CDN 路线已从“可能直接取得高清母版”降为低优先级监测项。只有出现新的客户端
resource revision、明确 quality 字段、iOS 合法包对照或官方公开媒体 URL，才重新
提升优先级；当前生产继续保持游戏原始 416x232/512x288 等尺寸，不做 upscale。
