# 2026-07-14 双音频母版 × 三字幕版本合同

最终发布单位不是“有字幕/无字幕”两版，也不是只做三种字幕，而是固定的 2×3
矩阵：

| audio master | no subtitles | Japanese | reviewed Chinese |
| --- | --- | --- | --- |
| `with_bgm` = BGM + original voice/SE | required | required | required |
| `no_bgm` = no BGM + identical voice/SE | required | required | required |

当前 MuMu 的 Sound Pack entitlement 是否开启，只影响运行时门控后的可听结果，
不能改变这个交付合同。

## 已实现的失败关闭门禁

核心实现：

```text
tools/frida_runtime_probe/subtitle_edition_contract.py
tools/frida_runtime_probe/composition_contract.py
tools/frida_runtime_probe/build_audio_base_masters.py
tools/frida_runtime_probe/render_subtitle_editions.py
tools/frida_runtime_probe/render_event_manifest.py
tools/frida_runtime_probe/build_series_editions.py
tools/frida_runtime_probe/build_scene_editions.py
```

`audio_master_contract` 现在要求：

- 每个 voice/SE 源文件的真实 path、SHA-256、role/identity、request/code、start、
  duration、source offset、原生 volume/unit，以及绑定到具体文件 hash 和 record locator
  的 runtime/static evidence；
- `no_bgm.bgm_layers` 必须为空；
- `with_bgm` 每个 BGM layer 必须有源文件/hash/resource ID、事件内 start/end、源播放
  phase、loop 与 loop points、初始 volume，以及严格有序的 duck/restore/fade/stop
  transition；evidence 必须覆盖 source/timing/volume/loop phase/transitions；
- 证据引用不能只是任意字符串，必须是存在的 artifact path + SHA-256 + record locator；
- 日文/中文必须逐 cue 共用同一时间轴，不自动翻译；两种语言可以绑定不同字体，
  每个字体都必须绑定真实文件/hash/family/source/license 并通过本语言全文 cmap；
  中文完整覆盖优先于与日文字体相同；
- 字幕排版不能继续使用硬编码 `Yu Gothic / FontSize=16`。有文字时必须提供一个日中
  共用、带证据的 game-layout profile，覆盖字号、颜色、描边、位置与安全区参数；
- verified base masters 必须共享完全相同的视频 packet，且 audio codec/sample rate/
  channels 签名一致；同一母版的三种字幕派生必须共享 audio packet hash，两个母版
  的 audio hash 必须不同；
- 字幕烧录保持原宽高、帧率、H.264 profile/level/pix_fmt，并以 base stream bitrate
  为目标，QA 超过容差就失败；不含 scale/upscale。

旧 `none+ja` 路径只在显式 `--legacy-two-edition` 时存在，属于历史 review 兼容，
不能晋升为新发布矩阵。

## 当前安全边界

该实现现在已经覆盖 clean visual、两条 base master、六版字幕派生、family series 和
跨 family scene 六路长片。关键实现边界如下：

- `render_event_manifest.py --clean-visual-only` 已对真实 ac7114/15/16 运行，逐帧、逐包
  时间轴 QA 均通过；它只生成原生尺寸 H.264 clean visual，不读取声音或字幕；
- `build_audio_base_masters.py` 从 clean visual 与完整 `audio_master_contract` 生成两条
  AAC 48 kHz stereo 母版，按 CFR 精确尾点计算有效音频样本数，区分 AAC raw padding
  与 container presentation samples，并在所有 sidecar 完成后最后写 READY；
- `render_subtitle_editions.py` 验证 READY、两条 sidecar、相同视频 packet/timeline 和
  不同有效 PCM，才派生 2×3；
- `build_scene_editions.py` 不再直接拼独立 AAC packet。它按每段 sidecar 的有效样本数
  解码裁剪、连续拼 PCM、每个 audio profile 单次 AAC 编码；视频仍 packet-copy，最后
  对六路逐帧/逐样本复核并原子发布 READY；
- 每个 modern scene 的 summary 位于本 scene 目录，后建 scene 不会覆盖旧 READY 的
  hash；JA/ZH SRT 必须逐 cue 精确匹配已审计 `edition_plan` 的数量/时间/文本，合并
  写出后再 round-trip 回读；presentation samples 按有理帧率计算并同时绑定 source
  event manifest、实际帧 timeline 与两路 audio sidecar，不假设恒为 30 fps；
- 旧 `none+ja` 只能显式 `--legacy-two-edition`，且不会被现代 READY 门禁接受。

尚未完成的是真实目标声音/字幕输入，而不是生成器骨架：ac7114/15/16 仍没有自然目标
同 run 的唯一 BGM ID、入口 phase、独立 VOL_EFCT/duck/stop 时间线，因此尚不能生成
可信 `with_bgm` 母版；日文游戏 layout metrics、中文字体缺字策略和人工批准的中文 cue
也未闭合。当前只生成了三条 clean visual，绝没有复制旧无 BGM 输出冒充六版。

真实 frame-grid 检查点：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\production_manifests_v20_frame_grid_20260715
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\validation_outputs_v20_clean_visual_ac7114_16_20260715
```

ac7114/ac7115/ac7116 分别为 289/666/391 帧，48 kHz presentation sample 数分别为
462400/1065600/625600；三条 clean visual 的 video frame/packet timeline QA 全部通过。
