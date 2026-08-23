# ac1102 旧“完整章节”代码级复核（2026-08-24）

## 结论

- 旧 91.8 秒 `R0052` 与 v77 的 16 个零碎路线都不再作为当前最终产品。
- DirInfo `kind=54` 共 31 行，事件并集是 15 个原生 416x232 完整 presentation；当前长片把这 15 个 presentation 各收一次，覆盖 31/31 路线，时长 4091 帧（约 136.366 秒）。
- 53 个原生视觉 occurrence 归并为 36 个字节唯一来源；完整 AV/subtitle presentation 的精确重复数为 0。源事件和别名记录仍保留。

## 代码权威

- CRIVideo 编译表 7801 项；22 个 authored MovieLayer 中 18 个可加载，4 个 `Add` 层代码不可达，而且均有同区间可加载 twin，因此旧“缺素材”阻断闭合为不可达层，而不是靠目测删层。
- 4 个旧缺事件 `_007/_013/_014/_015` 已用 runtime parent ranges 与 bounded source hash 重建。
- SOUND_DIVIDE_TBL `0x1445c54` 证明 request229/sound554 是 BGM；两次 occurrence 排除。15 条对白/SE 保留，7 条 caption voice 均有 event-global 起点，child-local-only 接受数为 0。

## 人工入口

- 当前唯一入口：`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\manual_review_native416_authoritative_longforms\CURRENT_REVIEW`
- `ZH\\story` 现有 ac7205、ac1103、ac1102 三个长片，共 3 个内容组；NONE/JP/ZH 不重复计组。
- MP4 是同卷 hardlink；源成品未移动、未删除、未转码。自动 QA 通过，人工播放待确认，尚未批准投稿。
