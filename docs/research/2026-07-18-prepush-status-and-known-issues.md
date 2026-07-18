# 2026-07-18 上传前状态与已知问题

## 本次同步边界

本检查点只同步已经完成的静态/动态研究、六版发布工具、审计文档和回归测试；不继续
启动新的 MuMu 捕获、逆向、渲染或批量生产。正确分支是
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

最终全仓回归：设置 `MAGIRECO_SLOT_ASSET_ROOT` 为耐久 D: 资源根后，289/289 tests
通过，0 skip/failure/error。负向测试会刻意输出若干 `ok:false`，最终 unittest 状态为
`OK`。

## 明确记录、尚未修复

### P1：重复 runtime event 静默 last-wins

`tools/frida_runtime_probe/build_event_production_manifests.py` 的
`load_runtime_event_manifests()` 对来自多个 runtime-manifest roots 的同名 event 仍会
用后读值覆盖先读值。若重复证据内容冲突，可能选择错误的语音/字幕/音频关系后继续生成
READY。后续修改应 fail closed 拒绝冲突重复；若内容完全等价，也应显式保存全部
provenance，而不是静默覆盖。

### 较低级：缩小集合重建可能残留旧 event JSON

production manifest output directory 目前不是整根 staging transaction。用更小事件集合
重建同一目录时，旧 `events/*.json` 可能残留。下游 expected-event-index 严格门禁会阻挡
一部分误用，但目录本身仍可能陈旧。后续应整批事务发布或按新 index 删除仅由该 builder
拥有、且不再属于集合的旧文件。

这些问题已公开记录，当前提交不把它们描述为已修复，也不据此生成新的正式成片。
