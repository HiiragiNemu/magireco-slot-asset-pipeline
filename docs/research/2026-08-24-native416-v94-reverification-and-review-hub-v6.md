# 既有 v94 原生 416 穷尽产品复核与统一审查入口 v6

## 结论

`native416_exhaustive_longform_checkpoint_v94_20260819` 的 6 个既有内容组已
按当前代码级标准重新校验并加入统一人工审查入口。没有重新编码媒体，也没有
为无字幕/静音产品制造重复语言审查文件。

新增内容组：

1. `ac4002` 回忆追逐动画：1 个事件；`none/JA/ZH` 原文件是同一 NTFS
   hardlink 与同一 SHA，只在 `NONE` 放一个 canonical 人工审查入口。
2. `ac4004` 火焰中的魔法少女动画：同样只审一个 canonical `NONE`。
3. `ac4003` 游乐园追逐动画：使用父级 inclusive cut 的 1300 帧边界，未采用
   child Z2D 的 1301 帧范围。
4. `ac7002` 夜空魔女战斗：5 个逻辑章节，6 个不同 CRI source identity 各
   保留一次；不再提供三秒独立片冒充最终产品。
5. `ac8005` Magius 玩法提示：7 个可见唯一 source；8 个 node-less control
   cut 排除，一个精确二进制 alias 合并。
6. `ac7118` 全角色资料动画：45 个不同资料 source；仅有的两个嵌入音轨解码
   为数字零，输出一个带有界静音 AAC 的 suffix-free `MATERIAL` 长片。

四个由穷尽构建器生成的产品重新执行 `--validate-only`，均通过计划结构、权威
文件、source hash、唯一 source 数与总帧数校验。`ac4002/ac4004` 重新验证了
`BATCH_REVIEW_READY.json`、QA、manifest 与三语言 alias 的 SHA/samefile。

## 当前唯一人工审查入口

`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\manual_review_native416_authoritative_longforms\CURRENT_REVIEW`

现指向：

`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\manual_review_native416_authoritative_longforms\releases\authority_v6_21families_20260824`

当前共有 21 个内容组、51 个文件入口：

- `NONE`：20；
- `JP`：15；
- `ZH`：15；
- `MATERIAL`：1。

其中 15 个有语言语义的长片保留三版；5 个 none-only 内容组只保留一个人工
审查入口；`ac7118` 只保留一个无语言后缀的 MATERIAL 文件。所有入口仍为
`HUMAN_PLAYBACK_REQUIRED`。

## 字面验证

`PASS_V94_REVERIFY groups=6 canonical_files=6 sha=6 ffprobe=6 native416=6 exact_aliases_ac4002_ac4004=4 samefile=4 blocked_leaks=0`

`PASS_DRY_RUN groups=21 editions=51 release=...\authority_v6_21families_20260824`

`PASS_PUBLISHED groups=21 editions=51 release=...\authority_v6_21families_20260824 current_updated=True`

`PASS_POST_PUBLISH current_target=v6 groups=21 editions=51 lanes=NONE20/JP15/ZH15/MATERIAL1 samefile=51 sha=51 ffprobe=51 native416=51 no_bgm=50 silent_material=1 p16_p17_p18_with_bgm_leaks=0`

定向回归：`Ran 7 tests in 0.202s`，`OK`。

最后代码状态的全仓回归：`Ran 811 tests in 120.236s`，
`OK (skipped=4)`；命令总耗时 `121.113s`。

`python -m py_compile` 与 `git diff --check` 同样通过。

## 绑定与回滚

- v6 计划：`tools/frida_runtime_probe/series_proposals/native416_authoritative_longform_review_hub_v6_20260824.json`
- 计划 SHA-256：`170CBE7C9DE27F32178D72457C01E2CFC618149CEAD1AA2B1B7CAB292A1D98AD`
- 索引 CSV SHA-256：`87876A7DC9F11EF3361D4AA4F2D8AB7CAF042E3DCD0CC6BBEB1741F369BB6E69`
- 索引 JSON SHA-256：`878E5F485F818001EB6BEC46EB6EFF0011224D8D7C5C340170E8BBC3D2B68D11`
- 验证记录 SHA-256：`5C774E661B02736C6A021BB530AB4CDA4E8B0CD376B623262301982B994DE833`
- v94 生产索引 SHA-256：`553B4A2239FC2C5EE06312237CE7685C6843DD81EB0F9479D528BBFF7BBA53AE`

旧 v5 junction 保存在：

`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\manual_review_native416_authoritative_longforms\current_links\CURRENT_REVIEW_before_authority_v6_21families_20260824`

回滚脚本：

`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\manual_review_native416_authoritative_longforms\releases\authority_v6_21families_20260824\ROLLBACK.ps1`

P16/P17/P18、child-local-only、512 组件与未闭合 with-BGM 均未进入 v6。
