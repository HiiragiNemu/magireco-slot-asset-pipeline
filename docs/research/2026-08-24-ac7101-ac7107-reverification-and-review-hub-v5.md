# ac7101–ac7107 代码级复核与原生 416 长片审查入口 v5

## 复核结论

`ac7101`–`ac7107` 的 7 个既有长片在重新运行生产计划输入校验、重新读取
静态/运行时权威与逐文件媒体验证后，仍满足当前“同 family 全部不重复完整
视频按可理解顺序合并”的收集标准，可进入人工播放审查：

- DirInfo/EventInfo 母集：7 个 family、21 个事件容器。
- 完整画面源：49 个 source identity；二进制唯一 49、完整解码序列唯一 49。
- 每组长片：3 个事件章节、7 个唯一 source identity、5130 帧、171 秒。
- `ac7101_001` 与 `ac7102_001` 各有一段局部画面重复（37 / 35 帧），但
  对应完整 AV 不同：较早窗口含非 BGM SE/非零 PCM，较晚窗口无该 cue 且
  PCM 静音。因此不能按“只看画面”删除，两个出现均正确保留。
- 14 个主要剧情事件均绑定 `event_global_parent_scene_motion_exact`；没有
  child-local-only 起点。
- 每个 family 的 `_003` 是精确 30 帧结果 source identity，只收录一次。
  其父级 hold 长度没有被冒充为已证明；这不影响“唯一源全收集”长片，但
  不得外推为原生单局 hold/loop 结论。
- 严格 no-BGM；P16/P17/P18、with-BGM 与 512 组件零泄漏。

权威文件：

`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\ac7101_ac7107_longform_authority_v97r1_20260819\LONGFORM_AUTHORITY.json`

SHA-256：`F12A39DC6F9C1C2D1CC62F0175AF998E78AB0588C449983920707E14F18C06FC`

## 进入统一人工审查的 7 组

1. `ac7101` 彩羽追寻愿望与忧全视频完整合集。
2. `ac7102` 桃子协助寻找忧并向八千代道歉全视频完整合集。
3. `ac7103` 鹤乃识破口寄神社与彩羽、忧重逢幻象全视频完整合集。
4. `ac7104` 菲利希亚品尝幸运水与杏子听闻 Magius 计划全视频完整合集。
5. `ac7105` 爱说明愿望并呼唤纱奈走向外界全视频完整合集。
6. `ac7106` 灯花与彩羽重新相识及麻美揭露魔法少女结局全视频完整合集。
7. `ac7107` 八千代追问 Magius 据点与黑江得知彩羽去向全视频完整合集。

统一入口仍为：

`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\manual_review_native416_authoritative_longforms\CURRENT_REVIEW`

现指向不可变 release：

`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\manual_review_native416_authoritative_longforms\releases\authority_v5_15families_20260824`

v5 合计 15 个内容组、45 个语言入口；`NONE / JP / ZH` 各 15 个 MP4。
这些都是同盘硬链接，不形成新的物理媒体副本。

## 字面验证

7 个计划重新校验均返回：

`PASS_VALIDATE_ONLY ... unique_source_count=7 total_video_frames=5130`

7 组既有成品重开验证：

`PASS_AC7101_AC7107_REVERIFY families=7 editions=21 unique_sources_per_family=7 frames_each=5130 duration_each=171.0 sha=21 ffprobe=21 native416=21 no_bgm=21 blocked_leaks=0`

v5 dry-run：

`PASS_DRY_RUN groups=15 editions=45 release=...\authority_v5_15families_20260824`

v5 发布与独立重开：

`PASS_PUBLISHED groups=15 editions=45 release=...\authority_v5_15families_20260824 current_updated=True`

`PASS_POST_PUBLISH current_target=v5 groups=15 editions=45 lane_counts=15/15/15 samefile=45 sha=45 ffprobe=45 native416=45 no_bgm=45 p16_p17_p18_with_bgm_leaks=0`

代码回归：

- 定向（包含复现并修正绝对临时路径偶含 `p18` 的旧误报）：`Ran 8 tests ... OK`。
- 全仓：`Ran 810 tests in 164.204s ... OK (skipped=4)`。
- `python -m py_compile` 与 `git diff --check`：exit 0。

## 绑定与回滚

- v5 计划：`tools/frida_runtime_probe/series_proposals/native416_authoritative_longform_review_hub_v5_20260824.json`
- 计划 SHA-256：`A3659FE406399A58214ACF08372B80388AFF538B4FC1D638EB9A181C317769EE`
- 索引 CSV SHA-256：`7937BE78DC507B58DFAF19F2789FA4B8B67308D41BA0AB873EA9D4B727C6CBB7`
- 索引 JSON SHA-256：`6FC18C9E4D9243608B43F3F90E35FAAD60DA72D3EAAC7E985E40882B23FB6CE9`
- 验证记录 SHA-256：`831758C8E67BEED25F9E2B0EE5B6B6ABD4360C9B255C3859337E44FC992533B0`
- v99 批次索引 SHA-256：`0C68B56CA37FD52826923CD5CCE4A06C670330296A8E96AA10DA96E02FD915C8`

旧 v4 未改动，原 CURRENT junction 保存于：

`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\manual_review_native416_authoritative_longforms\current_links\CURRENT_REVIEW_before_authority_v5_15families_20260824`

回滚脚本：

`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\manual_review_native416_authoritative_longforms\releases\authority_v5_15families_20260824\ROLLBACK.ps1`

自动 QA 与上述代码级闭合不等于人工播放批准；15 组仍全部标记
`HUMAN_PLAYBACK_REQUIRED`。
