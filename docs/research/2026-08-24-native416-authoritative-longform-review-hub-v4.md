# 原生 416×232 权威长片统一审查入口 v4

## 结论

现有 8 个已完成代码级穷尽审计、生产与自动 QA 的原生 416×232 family，
已汇入一个可复现、不可变的长片人工审查 release。每组仍保留 `none / JA /
ZH` 三个语义入口，但三版合计只算一个内容组。所有入口均为 D: 同卷 NTFS
硬链接；没有移动、复制、删除或重新编码源媒体。

当前唯一入口：

`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\manual_review_native416_authoritative_longforms\CURRENT_REVIEW`

它当前指向：

`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\manual_review_native416_authoritative_longforms\releases\authority_v4_8families_20260824`

## 内容组

1. `ac7205`：丘比新闻与魔女化身抉择；21 个事件容器、21 个不重复完整呈现。
2. `ac1103`：外送修行；13 / 13。
3. `ac1102`：菲莉希亚牧场；15 / 15。
4. `ac0908`：万万岁六种菜品；17 个事件容器映射到 14 个不重复完整呈现。
5. `ac1104`：香蕉船对决；17 / 17。
6. `ac1101`：沙奈猫锅挑战；13 / 13。
7. `ac7206`：阿莉娜绘画演出；14 个剧情事件 / 14 个完整 AV 呈现；独立玩法叠层 `ac7206_015` 未混入剧情长片。
8. `ac7210`：八千代与鹤乃火箭突击；5 个原生 416 剧情事件 / 5 个完整呈现；512 组件结局继续延后。

共 8 个内容组、24 个语言入口；`NONE / JP / ZH` 各 8 个 MP4。全部状态为
`AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED`，不得把自动 QA 外推为人工批准。

## 可复现构建

- 构建器：`tools/frida_runtime_probe/build_native416_authoritative_longform_review_hub.py`
- 绑定计划：`tools/frida_runtime_probe/series_proposals/native416_authoritative_longform_review_hub_v4_20260824.json`
- 计划 SHA-256：`AC64C11F821C57DEB6B7D4EE32B01C9D047310C2E7ABF28D08AECDA02777A47B`
- CSV 索引 SHA-256：`39B4EA90AD1C4B4D9C01A5EC9076326B066A1B18413011D574B36FF5119DC447`
- JSON 索引 SHA-256：`29773C3914D44D6C58099AD4BD7025A8162D27653A8EC3E8C0046A1AB10E9726`
- 验证记录 SHA-256：`F49E458FFBD186CCC8CC45ACB862E3F36FE2085305051E69F4611646EAD340E1`

构建器先绑定每组 `PRODUCTION_VERIFICATION.json`（`ac0908` 绑定其
`PRODUCTION_MANIFEST.json`），再逐源核对 SHA-256、首尾可读、416×232、
30/1、帧数、H.264、AAC 48 kHz stereo。发布阶段只允许同盘硬链接，并在
目标端再次核对 `samefile`、SHA-256 与 ffprobe 结果。release 已存在时会
fail-closed，不覆盖不可变产物。

## 字面验证结果

Dry-run：

`PASS_DRY_RUN groups=8 editions=24 release=...\authority_v4_8families_20260824`

发布：

`PASS_PUBLISHED groups=8 editions=24 release=...\authority_v4_8families_20260824 current_updated=True`

独立重开验证：

`PASS_POST_PUBLISH current_target=v4 groups=8 editions=24 lane_counts=8/8/8 samefile=24 sha=24 ffprobe=24 canvas=416x232 fps=30/1 h264_aac48k_stereo=24 p16_p17_p18_with_bgm_leaks=0`

代码回归：

- 定向：`Ran 5 tests ... OK`
- 全仓：`Ran 808 tests in 126.446s ... OK (skipped=4)`
- `python -m py_compile` 与 `git diff --check`：exit 0。

## 隔离与回滚

`P16/ac6003`、`P17/ac6004`、`P18/ac6005`、child-local-only、未闭合
with-BGM 与 512 组件均未进入本 release。旧 v3 release 未改动；原
`CURRENT_REVIEW` junction 已保存在：

`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\manual_review_native416_authoritative_longforms\current_links\CURRENT_REVIEW_before_authority_v4_8families_20260824`

可运行回滚位于：

`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\manual_review_native416_authoritative_longforms\releases\authority_v4_8families_20260824\ROLLBACK.ps1`

回滚只切换 `CURRENT_REVIEW` junction，不删除 release 或源媒体。
