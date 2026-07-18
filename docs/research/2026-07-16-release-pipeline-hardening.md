# 2026-07-16 六版发布流水线加固

## 结论

本轮在提交前用真实 FFmpeg 小媒体与故障注入重新审查了 event、scene、series 和
material 发布路径。发现的直接 AAC 拼接、旧 READY 被失败重跑破坏、SRT/来源 TOCTOU、
半成品目录、并发覆盖和 identifier-derived 输出路径逃逸问题均已修复；证据不足的媒体
仍保持 fail closed。

## Event audio base masters

`build_audio_base_masters.py` 保留原有逐包/逐帧/逐样本、decoded PCM、source rehash、
peak 和双 profile 门禁，并增加：

- 事件级跨进程 promotion mutex；
- out-root 同卷 staging；
- `os.link` no-replace 发布，READY 最后创建；
- 最终锁内再次检查目标；
- 只按 no-follow inode 身份回滚本进程拥有的链接，不覆盖或删除并发 sentinel/foreign
  replacement/另一完整 READY release。

竞态注入测试覆盖第二目标出现 sentinel、检查后出现完整 release、已发布目标被外部
替换三种情况。

## Event subtitle editions

`render_subtitle_editions.py` 现在：

- 每次写 SRT 后、FFmpeg 前后和 promotion 后都严格回读，逐 cue 比较
  `start_ms/end_ms/text`；
- 在批次开始/结束对 manifest、两条 base video、sidecar、READY 和字体做 SHA-256
  snapshot；
- 整批写入同级 staging，通过所有 worker/QA 后生成 batch READY 并 promotion；
- 任一 worker、1 ms 漂移、文本/缺 cue、渲染中来源变化或最终实体 rehash 失败时，
  正式根保持空或保留旧完整批次。

## Scene and series

`build_scene_editions.py` 不再在正式目录直接删除 READY/写文件。所有六版在同卷 staging
完成，最后可回滚切换；`overwrite=false` 遇已有 READY 时在创建 staging 前失败。第
4/6 个 mux 注入异常时，旧六版、manifest、READY 的 hash/mtime/size 均不变。

最终 mux 加入 `-copyts`，因此纯视频 concat 的合法非零首 PTS 不会被归零；最终 video
timeline SHA 必须与 canonical video-only SHA 相等。

`build_series_editions.py` 的 modern publication 路线不再 `-c:a copy` 拼独立 AAC：

1. 逐 event 验证 source manifest、两条 base-master sidecar、transaction READY、
   edition plan、SRT 和媒体 hash；
2. 按 sidecar `presentation_sample_count` 解码并精确 trim 有效 PCM；
3. 每个 audio profile 连续拼 PCM 后只编码一次 AAC；
4. none/JA/ZH 共用同一 profile 母版；
5. 运行 packet、decoded PCM、sample endpoint、video timeline 和 SRT round-trip QA；
6. 生成 series v4 manifest 与 series READY。

series 的 order/family refresh、component READY archive、六版媒体/SRT/manifest/READY
后验 hash 检查现在全部在 staging 内完成，最后只做一次可回滚目录切换。五个不同的
后验故障注入点均证明旧发布整树逐字节不变，且不残留 staging/previous 目录。

真实测试证明两段合并得到精确 48,000 presentation samples；旧直接 AAC concat 会被
presentation audit 拒绝。

## Material collections

`build_material_collection.py` 不再从“没有角色语音”反推纯素材。每个来源需 hash-bound、
人工批准的四类视觉语义：`material_effect`、`gameplay`、`story_animation`、`hybrid`。
BGM-only 剧情会保持 `story_animation`；没有音频的真实素材可生成 visual READY，audible
明确为 `not_applicable`。

audible review 现在按 `source_offset_ms/duration_ms` trim，并只应用证据绑定的 native
gain/fixed duck；删除无证据 limiter。事件中间体是 PCM，collection 最终只编码一次
AAC。缺音频合同会保留 visual 并把 audible 标成 `blocked_contract`；named route 不再
继承未绑定的 embedded AAC。整 collection 同样使用 staging、READY 和覆盖回滚；
manifest、READY、视觉/有声输出与 labels 的发布后 hash 任一失败时，坏新树会先隔离，
旧 READY 再原子恢复。首次发布失败也不会留下可见半成品。

direct route 现在把所有匹配的 production-manifest candidates（包括决定“不入选”的
候选）、实际视觉输入和官方音频输入纳入同一个 canonical source snapshot；named route
同样绑定 source plan、映射后的视觉/embedded-audio 文件及外部音频。构建开始与结束的
逐文件 size/SHA-256/role 快照必须完全一致，并写入 collection manifest；READY 同时绑定
start/end snapshot hash、source count、visual-label hash 与 audible-label hash。发布器会在
写 READY 前、目录切换前和切换后重新读取全部外部来源，且会在 staging 与发布树分别复核
两份 SRT 的实体 hash。production manifest、视觉源、音频源、named plan 在构建中被替换，
或来源/SRT 在 promotion 前后被替换的故障注入均 fail closed；已有 READY 整树保持逐字节
不变。

## Clean-visual event transaction

production manifest builder 现在为每个视觉 clip 写入 `source_sha256`，缺文件或缺 hash
都会使该 event fail closed。`render_event_manifest.py --clean-visual-only` 在渲染开始
逐 clip 核验绑定，并在完整视频 QA 后再次 rehash；中途替换、追加或删除任一来源都不会
得到发布。

clean visual、`render_manifest.json`、bound event manifest 不再依次写入正式 event
目录。完整候选先在 output root 同卷 sibling staging 中构建，清除 work 文件并最后写入
`magireco-clean-visual-release-ready-v1`；READY 逐项绑定三件成品。通过 staging QA 后
只提升整目录，promotion 后再次核验 READY、三件 hash 和相互路径/hash 绑定。覆盖时旧
完整目录先保留；promotion 后注入故障会隔离坏新树并恢复旧树，逐文件 bytes 不变。
旧 `--legacy-two-edition` 路径仍保留兼容性，但不会生成这个 READY，不能绕过生产合同。

## Output path contract

production-manifest builder、scene、series、material（含 `plan.collection` 重读）、
subtitle 和 event renderer 共用
`output_path_contract.py`。来自 CLI/manifest/plan 的逻辑 ID 只能是一个 Windows 可移植
路径组件；绝对路径、drive-relative、`..`、分隔符、NTFS ADS、保留设备名、尾点/空格、
控制字符均在任何 identifier-derived 媒体写入、promotion 或递归操作之前拒绝。解析后的候选路径还必须位于
声明的 output root 内，因此已有 symlink 也不能把写入或删除导向根外。Windows 真实
symlink 回归与六条生产入口 traversal 回归均通过且没有跳过。

## 验证与剩余边界

设置 `MAGIRECO_SLOT_ASSET_ROOT` 为 D: 耐久资源根后，全仓 289/289 tests 通过，0 skip/
failure/error；包含真实 JM/Noto cmap、真实 FFmpeg 时间轴/逐样本/事务、竞态注入和
observer bounded-state、发布后回滚和路径越界回归。全仓 `compileall`、三份 Frida JS
`node --check`、字体离线
hash/许可证校验、JSON parse 与 `git diff --check` 也通过。

这些修复关闭的是“构建器可能制造看似完整但边界错误/被部分覆盖的输出”风险，并不
替代内容证据。ac7114/15/16 仍需自然目标同 run 的 BGM ID/phase/volume/fade/duck/stop、
人工批准中文翻译与布局，然后才可实际生成并完整播放确认六版 event/scene。全库仍需
按 canonical event/video/voice/subtitle signature 批量推进 QA、series decision 和
material review。
