# 2026-07-27 人工审查与上传冻结交接

项目所有者已冻结新增生产。本检查点没有生成、重编码或修改任何源媒体，也没有
上传或修改 Bilibili；只把 v41 精确文件指南中已有的可投稿和待审文件整理为一个
耐久、可直接取用的人工交接包：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  bilibili_human_review_upload_freeze_20260727
```

交接包由
`tools/frida_runtime_probe/build_human_review_upload_freeze.py`
事务式生成。正式根存在时拒绝覆盖；构建期间任何失败只清理临时 staging。
源媒体均只读，194 个唯一媒体均通过同盘 NTFS hardlink 收录，没有 copy fallback。

## 队列

| 队列 | 作品 | 文件 | 批次 | 状态 |
| --- | ---: | ---: | ---: | --- |
| `00_UPLOAD_NOW` | 15 | 17 | - | exact-file 人工播放已批准 |
| `01_REVIEW_STORY` | 59 | 168 | 6 | 必须人工完整播放，禁止先上传 |
| `02_REVIEW_MATERIAL` | 11 | 11 | 2 | 必须人工完整播放，禁止先上传 |
| `03_QUARANTINED_DO_NOT_UPLOAD` | - | 0 MP4 | - | 只放说明，防止误传 |

`00_UPLOAD_NOW` 中有 15 个 ZH、2 个 JA、0 个 none。none 为空是因为当前没有
满足 exact-file 人工批准的 none 成片，不是省略其他待审 none；所有仍待审的
none 都在对应 `batch_###\none` 中。

剧情首批为：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  bilibili_human_review_upload_freeze_20260727\
  01_REVIEW_STORY\batch_001
```

首批 10 个作品、21 个 edition 文件、不同 exact hash 合计
770.523574 秒。每个待审批次内均按 `none`、`ja`、`zh` 分目录，同一 U 号用于
对应同一作品。全部批次均不超过 10 个作品或约 30 分钟的更严格边界。

## 可立即上传的范围

17 个 exact-file 批准只绑定以下产品和 edition，不外推 sibling edition：

- ac0908：一个明确标注为非单次原生流程的入口补全参考合集 ZH，以及
  DirInfo rows 52–57 六条独立菜品路线 ZH；
- ac7210：rows 0/1 两条路线 ZH；
- ac1102、ac1103、ac1104、ac5208：各一个已批准 ZH；
- ac4902/P12：纠错后的 JA、ZH；
- ac7117/P23：纠错后的 JA、ZH，标题保持“黑江与黑的相遇”。

逐文件目标 BV、绝对路径、精确文件名、建议分P名、追加/新建建议、自动 QA 和
人工状态均以 `manifests/UPLOAD_INDEX.csv` 为准。Bilibili 只读基线为：

- ZH：`BV13bKN6nEsd`（24P）；
- none：`BV1rUKN6iEcj`（11P）；
- JA：`BV1zQKN6eEC6`（13P）。

Codex 不执行上传。

## 合法跨目标别名

交接包共有 196 个命名入口、194 个唯一 SHA-256。唯一重复组是 ac4903
DirInfo row 8 的 none/JA/ZH，三者因无可见字幕差异而字节完全相同：

```text
2314C5055CC285B4077CB95D8FD2B8C276344B25A863B3E85ABB193214ABA4E6
```

none 是 canonical 文件；JA、ZH 各保留独立目标目录和正确命名的 hardlink，
三者实际指向同一物理数据。`ALIASES.csv` 和 `UPLOAD_INDEX.csv` 均记录相同
`canonical_sha256`、各自目标 BV 及 `physical_duplicate=false`。这类跨目标
别名是合法上传入口，不属于同一目标/同一语义的意外重复。

## 排除边界

P16/ac6003、P17/ac6004、P18/ac6005 全 family 继续隔离。P17 已知 child-local
起点被错误提升为 event-global 且漏 req3260；P18 人工确认声音、字幕早于张嘴；
P16 的父 DGM 到子 Z2D 实例化偏移仍未闭合。所有 superseded、旧错误/重复、
已投稿的 10 个 exact hash，以及未进入 v41 精确指南的未闭合 child-local 项目
均未进入媒体队列。隔离目录内没有 MP4。

身份合同不变：黑羽（黒羽）、黑（黒）、黑江（黒江）是三人；
`speaker_code=kuro` 不得全局映射，`kuroe` 才是黑江。

## 清单和完整性

```text
manifests\START_HERE_UPLOAD_GUIDE.md
manifests\UPLOAD_INDEX.csv
manifests\ALIASES.csv
manifests\SHA256SUMS.txt
manifests\HUMAN_REVIEW_CHECKLIST.md
manifests\EXCLUSIONS.md
manifests\PACKAGE_SUMMARY.json
```

关键清单 SHA-256：

- `START_HERE_UPLOAD_GUIDE.md`：
  `1D1EAE78D7E8367F3652AE16DE6561EAEDDC590C099568832EA0CDBA2133BD6D`
- `UPLOAD_INDEX.csv`：
  `7A4CD45A8B459265E67DAF48C778BF89345A85B2A6CEB46390C2EB5AD98B90C9`
- `ALIASES.csv`：
  `399453922036F4AF263974A531151AF1E297120A68628BAF67E9297C1B3C733D`
- `SHA256SUMS.txt`：
  `029CE6FF8DD063BF808363D7258DF1AD8557C74B1C530F21A78088491C803F60`
- `PACKAGE_SUMMARY.json`：
  `C18204D5BCBEC47DE2690236E4A6B166F9B585E216027E32824C2E72F15AB150`

独立复核重新读取并散列全部 196 个交接 MP4 和 `SHA256SUMS.txt` 中的 204
个条目，确认 196/196 命中预期 SHA-256；194 个源 canonical 均与交接文件
`samefile`，2 个别名均与其 canonical `samefile`。没有 copy fallback，没有
隔离媒体泄漏。

从本检查点起停止新增 family、渲染、逆向、BGM 和素材扩产，等待项目所有者
人工审查与上传。
