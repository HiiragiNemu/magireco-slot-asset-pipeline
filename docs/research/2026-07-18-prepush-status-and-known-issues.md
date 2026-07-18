# 2026-07-18 上传前状态与已知问题

## 本次同步边界

本检查点同步已经完成的静态/动态研究、六版归档工具、独立 R1 发布工具、首个 D: 人工
播放候选、审计文档和回归测试；候选自动 QA 后不继续启动新的 MuMu 捕获、逆向、第二部
渲染或批量生产。正确分支是
`codex/corrected-runtime-pipeline`。D: 的 `main@50e4f5d` 是干净历史 checkout，
`origin/main` 已不存在，不纳入本次提交，也不删除。

待提交内容均为文本源文件/文档/JSON：没有 MP4、音频、APK、native library、字体二进制、
缓存、凭据或密钥。固定 Noto 字体只保存依赖清单与 hash，17.8 MB 本地缓存继续由
`.gitignore` 排除。

## 本次已修复并验证

- material direct/named collection 对 manifest/plan、视觉源、音频源做构建前后完整
  source snapshot；READY 前、promotion 前后重哈希。visual/audible label SRT 的 hash
  同时写入 manifest/READY 并在 staging 与发布树复核，失败恢复旧 READY。
- clean-visual production manifest 为每个 clip 绑定 `source_sha256`；renderer 在开始与
  结束重哈希。三件成品与 READY 在同卷 staging 完成后以整 event 目录事务发布，晚失败
  恢复旧整树。
- subtitle batch 只有显式 `--overwrite` 才替换已有发布根；output root 与 manifest、
  base master 或其他快照来源存在祖先/后代重叠时在 staging 前拒绝。
- production manifest、scene、series、material、subtitle 和 event renderer 共用输出
  identifier/path containment，拒绝 traversal、drive/ADS、Windows 保留名和 symlink
  根外逃逸。
- series/material 的 post-promotion 故障不会再删除旧 READY；scene/series/material
  音频按 sidecar 样本边界连续 PCM 合并，每个 profile 最终只编码一次 AAC。

最终全仓回归：设置 `MAGIRECO_SLOT_ASSET_ROOT` 为耐久 D: 资源根后，307/307 tests
通过，0 skip/failure/error。负向测试会刻意输出若干 `ok:false`，最终 unittest 状态为
`OK`。

## 本轮新增关闭

### P1：重复 runtime event 静默 last-wins 已关闭

`tools/frida_runtime_probe/build_event_production_manifests.py` 的
`load_runtime_event_manifests()` 现在会先去除 loader 管理的 provenance 字段，再比较
来自多个 runtime-manifest roots 的同名 event：内容冲突立即 fail closed；内容完全
等价才允许继续，并保存每一份来源的绝对路径与 SHA-256。production manifest 通过
`runtime_event_manifest_sources` 公开全部 provenance，禁止后读值静默覆盖先读值。
新增正向/负向测试覆盖等价重复和冲突声音证据。

## 明确记录、尚未修复

### 较低级：缩小集合重建可能残留旧 event JSON

production manifest output directory 目前不是整根 staging transaction。用更小事件集合
重建同一目录时，旧 `events/*.json` 可能残留。下游 expected-event-index 严格门禁会阻挡
一部分误用，但目录本身仍可能陈旧。后续应整批事务发布或按新 index 删除仅由该 builder
拥有、且不再属于集合的旧文件。

该较低级问题继续公开记录；首个独立 R1 使用全新的版本化 output root，未复用缩小集合
的旧 production-manifest 目录。它不影响本轮 P1 已关闭的结论。
