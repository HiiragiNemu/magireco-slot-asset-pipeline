# ac0908 “六种菜品入口补全合集”逆向后权威结论（2026-08-24）

## 结论

旧 `A0007`/001-009 合集保留历史人工通过事实，但在“穷尽游戏内所有对应视频”的新标准下不再完整：它只覆盖 001-009，并重复 009，漏掉五个代码级唯一结局呈现。

当前 v102 长片是新的人工审查对象：

- 17 个 event container 全覆盖；按 pointer-free runtime cut/node/motion/key 结构归并为 14 个代码级唯一完整呈现。
- `_013/_014/_015` 是 `_010/_011/_012` 的精确呈现别名，只展示一次；事件记录仍保留。
- 顺序是饭店外景/侧身炒菜入口、强入口、六种菜品、公共收尾、HATTEN/CZ/WIN/PREMIA/ZENCHOU 五种结局。
- 精确视觉最小值 3751 帧；因已验证对白/SE 尾部延长，最终长片 3915 帧（130.5 秒）。只在音频超出视觉 cut 时保持尾帧。

## 代码级证据

- Exact Slot `libGameProc.so` SHA-256：`5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF`。
- EventInfo 与 runtime Direction scene/cut 证明 17 个事件容器、并行 event-global 起点与 14 个唯一结构。
- 编译 CRI filename table 与 `LoadUSMFileByName` 路径证明 `_016` 的 `add/add_LP` 虽被 authored，但当前 binary 无法加载；`base/base_LP` 可加载，因此不是缺媒体。
- SOUND_DIVIDE_TBL 排除 551/552/553 的 6 个 BGM occurrence，保留已验证对白与 SE。机器视觉未作为权威。

## 人工入口

`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\manual_review_native416_authoritative_longforms\CURRENT_REVIEW`

现在共有 4 组内容；请优先播放 `ZH\\story`。ac0908 文件名为 `万万岁六种菜品_全入口全结局完整合集_ac0908__zh.mp4`。自动 QA 通过，人工待确认，尚未批准投稿。
