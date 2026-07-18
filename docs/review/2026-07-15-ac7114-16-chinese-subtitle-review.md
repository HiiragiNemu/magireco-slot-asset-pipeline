# ac7114/15/16 中文字幕人工审阅单

状态：**DRAFT / NOT HUMAN APPROVED / NOT RELEASE-ELIGIBLE**

本文件只把 v20 production manifest 中已经审核过时间轴的 10 条日文 cue 转成中文
候选，供项目所有者逐条确认。它不是 production translation contract，不设置
`human_approved=true`，也不能被六版 renderer 当作已批准中文字幕。任何修改都必须
保持对应日文 cue 的 `start_ms` / `end_ms` 不变。

## 来源锚点

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\production_manifests_v20_frame_grid_20260715\events\ac7114_001.json
SHA-256 07BAF3D26169DCC26C7C64B6F450004BE4C87E117FD13A50734959AB51F27A89

D:\magia\MyProducts\casino\magireco_corrected_research_20260612\production_manifests_v20_frame_grid_20260715\events\ac7115_001.json
SHA-256 F0444CB9E3686C0EB224C3E58F48C57C2A03A9BCCDA526D0EF692899EAE92A5F

D:\magia\MyProducts\casino\magireco_corrected_research_20260612\production_manifests_v20_frame_grid_20260715\events\ac7116_001.json
SHA-256 F57DE76B29131E8373C0A604BFDDD85584EA9489E40795602F7C99FDDFF490D9
```

## 待审阅中文

| Event | 时间（ms） | 说话人代码 | 官方日文 | 中文候选 | 人工决定 |
| --- | ---: | --- | --- | --- | --- |
| ac7114_001 | 1450–6137 | tur | 鶴乃ちゃんハ サイキョー ダレヨリモツヨイ | 鹤乃酱是最强的，比任何人都强。 | 待审阅 |
| ac7114_001 | 6081–8648 | iro | 嘘ついちゃダメだよ！ 鶴乃ちゃん！ | 不可以说谎啊！鹤乃酱！ | 待审阅 |
| ac7114_001 | 8806–9629 | yac | 鶴乃…！ | 鹤乃……！ | 待审阅 |
| ac7115_001 | 2354–3450 | iro | かえでちゃん！ | 枫酱！ | 待审阅 |
| ac7115_001 | 3357–3926 | kuroe | あれは… | 那是…… | 待审阅 |
| ac7115_001 | 4224–6754 | rena | かえで！ しっかりして！ かえで！ | 枫！振作一点！枫！ | 待审阅 |
| ac7115_001 | 7622–12663 | kae | レナちゃん… | 玲奈酱…… | 待审阅 |
| ac7115_001 | 9667–11533 | graphical-only | ごめんね… | 对不起…… | 待审阅；该行是画面文字，不绑定语音 |
| ac7115_001 | 19821–22167 | rena | かえで… | 枫…… | 待审阅 |
| ac7116_001 | 8783–13027 | mihu | く…ぐ… | 唔……呃…… | 待审阅；拟声语气尤其需要听检 |

注意：ac7114 第 1、2 行和 ac7115 第 1、2 行存在官方 cue 时间重叠；这里原样保留，
不是翻译端自行合并。ac7115 的“ごめんね…”已经由 composition plan 明确为
graphical-only，不得重新附会到旧 request 8894。

## 游戏 JM 字形覆盖实测

覆盖检查使用只读源：

```text
libGameProc.so SHA-256 5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF
dgi.bin       SHA-256 4D5FD52F6DD61D33B5A0EC6576BC9841089AE8B91BCAB262C0E9B3E1E17F487E
dgi_add.bin   SHA-256 7F1DE69AD59856E85F46012D8AA31E853D5EEA8810D5B70FD4BD469A3330A836
```

对上表中文候选做 `extract_jm_dgi_glyph_catalog.py --coverage-text` 实测：34 个非空白
码点中 19 个覆盖、15 个缺失，门禁失败。缺失码点为：

```text
U+5443 呃    U+5514 唔    U+554A 啊    U+5948 奈    U+5BF9 对
U+5F3A 强    U+662F 是    U+67AB 枫    U+73B2 玲    U+8BF4 说
U+8C0E 谎    U+90A3 那    U+9171 酱    U+9E64 鹤    U+FF0C ，
```

完整 4,124-glyph JSON 审计已写入耐久 D:（4,796,659 bytes）：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\subtitle_review_v20_20260715\ac7114_16_zh_candidate_jm_coverage.json
SHA-256 6B9DAC7F6E0FF99D41029B9EE208A7AEE4CB50A5128589806736ED55C21658C3
```

所以“中文与日文完全使用同一原生 JM 字形”在当前候选上不可行。发布前必须二选一并
显式记录：补做经过审计、视觉风格匹配且覆盖全部缺字的 fallback 字体；或由人工改写
中文并重新跑全码点覆盖。无论选择哪条路线，都不能把 fallback 称为游戏原生字形，
并仍需从 Z2D/runtime 关闭字号、基线、描边、位置和安全区参数。

## 人工批准后才可执行

1. 项目所有者逐条确认或改写“中文候选”，尤其确认角色名用“枫/玲奈/鹤乃”及
   “酱”的风格是否符合预期。
2. 生成正式 translation records，每条保存日文 source-cue hash、译者或翻译方法、
   审阅者、时间戳和明确的 `human_approved=true`。
3. 对最终中文全文重新运行 JM + fallback cmap 覆盖检查，缺一个码点即失败。
4. 用与日文相同的已验证 game-layout profile 生成小样，人工检查遮挡、换行与安全区。
5. 小样批准后才允许进入 ac7114/15/16 的两音频母版 × 三字幕六版长片。
