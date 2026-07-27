# Project Status

更新时间：2026-07-27

## 2026-07-27 ac7211 三尺寸角色组件 v56

`material_collections_v56_ac7211_split_components_review_20260727` 已把
ac7211 当前完全解析的 15 个事件拆成三个原生 visual-only 产品：33 个
416x232 角色序列源、5 个 512x288 的 event014 角色序列源，以及 1 个
被 15 个事件复用的 192x320 角色立绘待机源。39 个唯一源、53 个
occurrence 均闭合，与此前 current material index 零重叠。两条内嵌
ALAC 轨均为 -91 dB 数字静音，正式输出丢弃静音轨；不猜成对白、SE 或
BGM。

覆盖审计为 15/15 event、39/39 source、0 unused。三个尺寸保持独立，
没有拉伸、补边、upscale、跨尺寸 composition 或自然 session 声明。
`ac7211_002–004` 与 `_016–018` 仍未解析并明确排除。

当前总账为 `production_ledger_v24_20260727`：produced audience 195、
material-covered 618、produced DirInfo route 79、timing blocker 330、
quarantine audience 53。正式指南 `upload_guide_v56_20260727` 为
10 已投稿、17 可投稿、314 待人工播放、8 排除，共 341 个精确文件。
U137/U138/U139 分别是 416x232、512x288、192x320 审查入口，三者
`UPLOAD_NOW` 均为 0。详见
`docs/research/2026-07-27-ac7211-split-native-component-checkpoint-v56.md`。

## 2026-07-27 ac8005 六条独立玩法告知路线 v55r2

`production_manifests_v55r1_ac8005_six_silent_gameplay_routes_20260727`
闭合了 DirInfo kind 214 的 rows 0–4、13：`ac8005_001–005` 与
`ac8005_014`。六条均为 selector 0 的单事件、单层、原生 416x232、
exact-duration、非循环画面；direct-parent audio、child-Z2D audio、
subtitle 三个哈希绑定目录均为零匹配。总计 2,460 帧／82 秒。

成品根
`no_bgm_editions_v55r1_ac8005_six_silent_gameplay_routes_review_20260727`
包含 6 个相互独立产品、18 个 none/JA/ZH 目标文件；每个产品三轨是合法
同哈希 hardlink。它们属于玩法／告知动画，不是剧情或自然游戏 session，
禁止把六条 sibling 路线机械串联。

正确人工审查根是
`bilibili_incremental_review_v55r2_ac8005_gameplay_six_routes_20260727`：
U131–U136 全部位于 `02_REVIEW_MATERIAL\batch_001`，没有媒体进入
`01_REVIEW_STORY` 或 `UPLOAD_NOW`。目标是三个新建的原生416玩法／告知
none、JA、ZH 合集，不指向现有剧情 BV。先前 `v55r1` guide/review 错误
使用剧情目标与剧情队列，已被 v55r2 supersede，禁止上传；媒体生产根不受
该元数据纠正影响。

总账当前为 `production_ledger_v23_20260727`：produced audience 195、
material-covered 603、produced DirInfo route 79、timing blocker 330、
quarantine audience 53。正式全局指南 `upload_guide_v55r2_20260727`
为 10 已投稿、17 可投稿、311 待人工播放、8 排除，共 338 个精确文件。
`ac8005_012` 的 loop 合同及 4 个原生 512x416 component-only 事件未混入。
详见
`docs/research/2026-07-27-ac8005-independent-silent-gameplay-checkpoint-v55r2.md`。

## 2026-07-27 ac7118 有限资料型产品 v54r1

当前正式总账为 `production_ledger_v22_20260727`，正式全局上传指南为
`upload_guide_v54r1_20260727`。本检查点只新增 `ac7118_001`：DirInfo kind
194 row 0 精确绑定该事件；两个原生 416x232 来源分别是 100 帧开场和
600 帧 `orphan_loop_cycle`。当前目录对 direct-parent audio、child-Z2D
audio、subtitle 都是零匹配。

成品根 `no_bgm_editions_v54r1_ac7118_profile_bounded_review_20260727`
包含 none/JA/ZH 三个目标入口，均为同一 23.333 秒 exact SHA 的合法
hardlink alias。产品合同明确限定为“开场＋恰好一遍完整源循环”；它不宣称
自然运行时会话、运行时循环次数或自然停留时长。人工审查入口为
`bilibili_incremental_review_v54r1_ac7118_profile_bounded_20260727` 的 U130，
`UPLOAD_NOW` 为 0。

总账当前为 produced audience 189、material-covered 603、produced DirInfo
route 79、timing blocker 330、quarantine audience 53。指南当前为
10 已投稿、17 可投稿、293 待人工播放、8 排除，共 320 个精确文件。
先前未正确传递布尔／loop scope 的两个 v54 试验根不是 current，禁止上传；
唯一 current 来源带 `v54r1`。P16/P17/P18 继续 hard quarantine，正式
with-BGM 候选仍为 0。详见
`docs/research/2026-07-27-ac7118-bounded-profile-material-checkpoint-v54r1.md`。

## 2026-07-27 ac0916 三尺寸玩法组件 v53

`material_collections_v53_ac0916_split_components_review_20260727` 已把
ac0916 的 104 个 mixed 玩法／效果事件、652 个 exact occurrence 拆成
3 个原生 visual-only 产品：23 个 416x232 角色动作源、4 个 416x120
文字入场源、12 个 160x120 文字循环效果源。39 个唯一源与 v20 current
material index 零重叠；没有跨尺寸拼接、缩放或自然事件声明。

覆盖审计为 104/104 event、652/652 occurrence、39/39 source、0 unused。
总账推进到 `production_ledger_v21_20260727`：produced audience 188、
material-covered 603、produced DirInfo route 79、timing blocker 330、
quarantine audience 53。全局指南 `upload_guide_v53_20260727` 为
10 已投稿、17 可投稿、290 待人工播放、8 排除，共 317 个精确文件。
U127/U128/U129 分别是 416x232、416x120、160x120 审查入口，三者
`UPLOAD_NOW` 均为 0。

`ac0903_001` 的事件、层区间和 req680 时序已闭合，但 native add/mlt 的
blend、色彩／alpha、最终 z-order、canvas transform 与量化合同未闭合；
`composition_blockers_v53_ac0903_20260727` 明确记录不允许渲染且媒体数为 0。
详见
`docs/research/2026-07-27-ac0916-split-native-component-checkpoint-v53.md`。

## 2026-07-27 ac4902 新入口路线与 ac0905 分尺寸组件 v52

`no_bgm_editions_v51_ac4902_selector_entry_routes_review_20260727` 已产
17 条独立原生 416x232 DirInfo 路线、51 个 none/JA/ZH MP4；9 条精确
audience alias 行没有重复渲染。三种入口事件均用 event-global 0 的
direct-parent action SE，child audio/subtitle 为零；路线尾部复用已获人工
批准的 P12 v26 主片。builder 会校验源主片仍含两句获授权的
`黑羽：可恶！`，但这 17 个路线切片本身不含这两句。没有跨互斥路线
showcase。

`material_collections_v52_ac0905_split_components_review_20260727` 只覆盖
8 个 mixed 事件：8 个原生 416x232 SU 玩法组件与 7 个原生 512x416 效果
框。覆盖审计为 8/8 event、15/15 source、16/16 occurrence；其他 8 个
full-frame-only 事件和未绑定的 `ac0905_SU3_ef_waku_S_2` 继续阻断。

当前正式总账为 `production_ledger_v20_20260727`：produced audience 188、
material-covered 499、produced DirInfo route 79、timing blocker 330、
quarantine audience 53。v19 只是一份在发布前发现 singular
`dirinfo_source_row` 漏计的失败审计根，不是 current。全局指南
`upload_guide_v52_20260727` 为 10 已投稿、17 可投稿、287 待人工播放、
8 排除，共 314 个精确文件。

ac4902 人工审查分 U108–U117 与 U118–U124 两批；ac0905 为 U125/U126。
四个增量审查根的 `UPLOAD_NOW` 与 quarantine media 均为 0。详见
`docs/research/2026-07-27-ac4902-selector-entry-and-ac0905-components-checkpoint-v52.md`。
P16/P17/P18 继续 hard quarantine；正式 with-BGM 候选仍为 0。

## 2026-07-27 ac5001 分尺寸飞行组件 v50

`material_collections_v50_ac5001_split_components_review_20260727` 已把
ac5001_001–036 的 287 个 exact visual occurrence 拆成两个原生尺寸产品：
15 个 416x232 飞行动作／背景／属性组件（55.663 秒）和 1 个 512x416 攻击
标题组件（2.5 秒）。没有跨尺寸拼接或 upscale；`ac5001_007` 特有的 7 组件
集合保持原样，没有错误补入其他 35 个事件共有的 `ac5101_1G_lev_lp`。

覆盖审计 `material_component_coverage_v50_ac5001_20260727` 通过：
36/36 event、287/287 occurrence、16/16 唯一源、0 unused。两个 manifest
对 v17 当前素材库存的 source SHA 重叠均为 0。它们只声明 visual component
coverage，不冒充完整事件、对白／SE／BGM／字幕或自然 session。

总账推进到 `production_ledger_v18_20260727`：produced audience 185、
material-covered 491、produced DirInfo route 62、timing blocker 330、
quarantine audience 53；P16/P17/P18 继续 hard quarantine。全局指南
`upload_guide_v50_20260727` 为 10 已投稿、17 可投稿、234 待人工播放、
8 排除，共 261 个精确文件。U106/U107 分别位于 416x232 与 512x416
增量审查根；none/JA/ZH 是合法跨目标 hardlink，全部待人工播放，
`UPLOAD_NOW` 为 0。

当前严格 natural silent-story 门禁已无新增候选：不能因未找到音频行就继续
扩大 v48 通道。后续 `ac7118_001` 是明确标注“开场＋一遍源循环、非自然会话”
的资料型例外，不推翻这项结论。正式 with-BGM 候选仍为 0；继续从 ledger v18
穷尽 no-BGM。详见
`docs/research/2026-07-27-ac5001-split-native-component-checkpoint-v50.md`。

## 2026-07-27 ac905x 分尺寸连打组件 v49

`material_collections_v49_ac905x_uwanose_split_components_review_20260727`
把 ac9051_031–040、ac9053_011–020、ac9060_001 共 21 个玩法／效果事件共享
的 5 个精确组件，按原生尺寸拆成 3 个 visual-only 审查产品：416x232 背景与
冲击层（10 秒）、144x160 G/Plus 计数层（8 秒）、128x64 总计数层（8 秒）。
没有缩放、没有跨尺寸拼接；由于冲击层的 event-global 区间尚未闭合，这些
只是原始组件目录，不冒充事件或自然 session 时间线。

跨 family 覆盖审计
`material_component_coverage_v49_ac905x_20260727` 通过：21/21 event、
105/105 occurrence、5/5 唯一来源全部覆盖。新增当前素材来源重叠门禁会重哈希
当前 index 与所有 current manifest；本批 0 重叠，128x64 单来源也只保留一次，
未伪造重复。

总账推进到 `production_ledger_v17_20260727`：produced audience 185、
material-covered 455、produced DirInfo route 62、timing blocker 330、
quarantine audience 53；P16/P17/P18 继续 hard quarantine。全局指南为
`upload_guide_v49_final_20260727`：10 个已投稿、17 个可投稿、232 个待人工
播放、8 个排除，共 259 个精确文件。U103/U104/U105 分别位于三个最终增量
审查根，每个产品的 none/JA/ZH 是一个物理文件的合法跨目标 hardlink，全部
待人工播放，`UPLOAD_NOW` 为 0。

ac7113_015、ac7115_007、ac7116_028 虽有原生 512 全帧画面与 0ms
direct-parent SP-story OGG，但该父音轨是否含对白／BGM 尚无逻辑证据；三轨
全部 fail closed，没有渲染。精确阻断写入
`direct_parent_story_soundpack_blockers_v1.json`。正式 with-BGM 候选仍为
0；继续从 ledger v17 穷尽 no-BGM。详见
`docs/research/2026-07-27-ac905x-split-native-component-checkpoint-v49.md`。

## 2026-07-27 精确无对白原生 416 与分尺寸素材 v48

生产冻结已解除；已完成的
`bilibili_human_review_upload_freeze_20260727` 继续保持只读、不覆盖。v48 新增
一条严格的无对白 audience lane：只有单事件 DirInfo、原生 416x232、精确
画面区间，并且 direct-parent audio、child-Z2D audio、subtitle 三个当前哈希绑定
目录对该事件都为零行时，才允许建立空音频／空字幕 manifest。ac4002_001、
ac4003_001、ac4004_001、ac7002_001 至 `_005` 共 8 个产品、190.667 秒通过；
`no_bgm_editions_v47_silent_native416_review_20260727` 已产 none/JA/ZH 24 个
目标入口。因为确实无对白／字幕，每个产品三轨是同哈希、同 inode 的合法
跨目标别名；AAC 为 48 kHz stereo，峰值 -91.0 dBFS。自动 QA 通过但全部仍待
人工播放，未进入 `UPLOAD_NOW`。

素材侧 `material_collections_v48_ac0504_ac4921_split_components_review_20260727`
新增 3 个 visual-only 审查产品：ac0504 11 个原生 416x232 胜利演出组件；
ac4921 的 6 个原生 416x232 角色动作与 10 个原生 416x120 结果框分开保存，
不缩放、不跨尺寸拼接。ac0504 的 event variant 区间仍有歧义，因此只作原始
组件合集，不冒充事件时间线；ac4921 的 22-event 覆盖审计通过。

总账推进到 `production_ledger_v16_20260727`：当前 produced audience event
185、material-covered 434、produced DirInfo route 62、timing blocker 330、
quarantine audience event 53。P16/P17/P18 仍为 hard quarantine。正式全局
指南为 `upload_guide_v48_final_20260727`，共 10 已投稿、17 可投稿、229 待
人工播放、8 明确排除、256 个精确文件；中间 v48 指南已标 superseded。
增量审查入口为：

```text
bilibili_incremental_review_v48_silent_native416_final_20260727
  U092-U099，8 个产品 / 24 个目标文件
bilibili_incremental_review_v48_material_native416x232_final_20260727
  U100-U101，2 个产品 / 6 个目标文件
bilibili_incremental_review_v48_material_native416x120_final_20260727
  U102，1 个产品 / 3 个目标文件
```

MuMu/Frida 的耐久恢复记录已合入本检查点：旧 17.5.2 会污染 Android 15
zygote；唯一验证组合为 Frida 17.16.4、frida-tools 14.10.4、device server
17.16.4、ARM64 Gadget 17.16.4。`reproducibility/toolchain.lock.json` 已同步，
Git 不包含二进制。当前正式 with-BGM 候选仍为 0；继续从 ledger v16 扩展
no-BGM，只有全部已发现库存已产或精确阻断后才切换。详细证据见
`docs/research/2026-07-27-silent-native416-and-split-material-checkpoint-v48.md`。
最终代码状态全仓回归为 445 passed / 4 skipped；compile、JSON parse、
diff check 与审查包 hardlink/hash 核对均通过。

## 2026-07-27 ac5102 分尺寸组件覆盖 v46

`material_collections_v46_ac5102_split_components_review_20260727` 已生成
ac5102 的原生 416x232 视觉组件目录：116 个混合尺寸事件映射到 49 个
去重片段，成片 45.429 秒、30fps、H.264、无音轨、无字幕，SHA-256
`D067F5393576CF4A85EF9105A30571A18DF25DC39913B252E1588078D0707357`。
同一批事件所需的 8 个原生 512x288 按钮片段不重复生产，精确复用 v44
机会按钮目录；两种原生尺寸没有互相放大，也没有机械拼为假事件时间线。

新增 fail-closed 跨目录审计
`material_component_coverage_v46_ac5102_20260727`。它重新哈希 v14 的
120 条 ac5102 event manifest、两个素材 manifest、两个输出及所有源 MP4，
逐事件核对 416 component map 和 512 按钮来源。审计结果为 120/120
事件、57/57 实际使用的唯一片段全部覆盖；v44 中另两个通用按钮片段被明确
标为允许未使用。覆盖只说明视觉组件库存闭合，不说明对白、SE、字幕、
child-local 时序或游戏自然 session 已闭合。

增量审查根
`bilibili_incremental_review_v46_ac5102_split_components_20260727` 使用 U091：
none/JA/ZH 三个入口为同一无声源的同 inode hardlink，`physical_duplicate`
均为 false。`00_UPLOAD_NOW` 为 0；唯一内容 45.429 秒，仍须所有者完整播放。

总账推进到 `production_ledger_v15_20260727`：22 个当前素材 manifest 加
1 个分尺寸覆盖 bundle，material-covered event 288→408。当前 926-event
production-manifest 库存中已无 `planned_unproduced`：168 个剧情事件已产、
408 个素材／玩法事件已覆盖、330 个因 child-local 时序阻断、20 个属
P16/P17/P18 隔离。这个收口不等于更大的 audience/DirInfo 母集已完成：
后者仍需继续做现代 manifest、分类和路线证据审计。

全局指南 `upload_guide_v46_20260727` 为 10 个已投稿、17 个可投稿、
202 个待人工播放、8 类明确排除，共 229 个精确文件。P16/P17/P18、
所有未闭合 child-local 项和 superseded 继续 fail-closed；冻结交接包保持
不变。当前正式 with-BGM 候选仍为 0，不能仅因 926-event 子库收口便提前
切换。详细证据见
`docs/research/2026-07-27-ac5102-split-native-component-coverage-v46.md`。

## 2026-07-27 其余纯原生 512 玩法素材 v45

`material_collections_v45_native512_remaining_review_20260727` 已把
production-manifest 库存中除 ac5102 外的纯 512x288 玩法／效果事件全部收口：
ac3102、ac3103、ac3407、ac3409、ac8000 共 107 个事件，形成 5 个
visual-only 审查产品、210 个唯一命名片段、349.443 秒。全部为原生
512x288、30fps、H.264、无音轨、无字幕、直接复制视频包；自动技术 QA
通过，但仍为 `review_only` / `human_playback_required`。

具体产品为：ac3102 轮盘战斗 118 段、ac3103 轮盘颜色 32 段、ac3407
角色揭示 28 段、ac3409 角色揭示 28 段、ac8000 下一段剧情界面 4 段。
clip 清单不再人工抄写：构建器从哈希绑定总账指定的 107 个 v20 manifest
按 event/clip 顺序派生官方名称，再校验 official-name map 解析出的源 MP4
与 manifest 路径 exact SHA 一致。这批来源中的 378 个音频层与 150 条字幕
cue 均明确排除，未消费 child-local 时序。

增量审查根 `bilibili_incremental_review_v45_native512_remaining_20260727`
为 U086-U090：15 个 none/JA/ZH 命名入口、5 个唯一 SHA、10 个合法同 inode
别名，唯一播放时长 349.4431 秒；`00_UPLOAD_NOW` 和隔离媒体均为 0。

总账推进到 `production_ledger_v14_20260727`：material manifest 16→21，
material-covered event 181→288，`planned_unproduced` 227→120；剩余 120 个
全部属于 ac5102。全局指南 `upload_guide_v45_20260727` 为 10 个已投稿、
17 个可投稿、201 个待人工播放、8 类明确排除，共 228 个精确文件。详细
证据见 `docs/research/2026-07-27-native512-remaining-materials-v45.md`。

ac5102 的 120 个事件引用 49 个原生 416x232 clip 与 8 个原生 512x288
clip；下一检查点必须建立分尺寸组件目录及覆盖关系，不得把两种尺寸塞进同一
线性画布、不得 upscale。P16/P17/P18 与所有 timing blocker 继续隔离。

## 2026-07-27 原生 512 机会按钮玩法素材 v44

其他原生尺寸玩法／素材产线首先收口了在多个 family 中重复出现的 ac8002
机会按钮。`material_collections_v44_native512_chance_buttons_review_20260727`
包含一个原生 512x288、30fps、H.264、无音轨的视觉-only 合集：普通
CHANCE、按下、连击、长按、连打五类提示，各保留 intro/loop 一次，共 10
段、14.000 秒，SHA-256
`D2C2E4F08ABE40751976BAEF4E30F2D35FB9EA7BD04E4426923362D2654EBAC2`。

本合集覆盖 ac0909、ac6101、ac7221、ac8002、ac9051 共 59 个
gameplay/effect 事件。这 59 个事件的完整视觉 clip set 都只引用上述五组
按钮；来源总账、59 个 v20 manifest、官方名称表和 10 个源 MP4 均进入
source snapshot。原事件的 105 个音频层与 302 条字幕 cue 全部明确排除；
因此本合集不消费 child-local 时序，也不声称原事件的对白／SE 已修复。

增量审查根
`bilibili_incremental_review_v44_native512_chance_buttons_20260727` 使用 U085：
none/JA/ZH 三个入口为同一源 MP4 的同 inode hardlink，分别指向三个目标轨，
但仍全部 `HOLD_FOR_HUMAN_PLAYBACK`；`00_UPLOAD_NOW` 和隔离媒体均为 0。

总账推进到 `production_ledger_v13_20260727`：current material manifest
15→16，material-covered event 122→181，production-manifest
`planned_unproduced` 286→227；blocked timing 与 quarantine 数量完全不变。
全局指南 `upload_guide_v44_20260727` 为 10 个已投稿、17 个可投稿、196 个
待人工播放、8 类明确排除，共 223 个精确文件。详细证据见
`docs/research/2026-07-27-native512-chance-button-material-v44.md`。

剩余 227 个 production-manifest 玩法／效果事件集中在 ac3102（57）、
ac3103（24）、ac3407（12）、ac3409（12）、ac5102（120）和 ac8000（2）。
除 ac5102 外的五个纯 512 family/组可继续视觉-only 收口；ac5102 同时包含
原生 416 与 512 组件，必须分层建目录，不得线性拼接或把任一尺寸放大。

## 2026-07-27 其他原生尺寸 event-exact 单事件审查 v43

原生 416 剧情／路线的下一批已在 v42 核对为“无新增 event-exact natural
family”；因此产线按既定优先级进入其他原生尺寸，而不是重新生产低证据的
512 family 拼接。v43 在
`no_bgm_editions_v43_event_exact_512_review_20260727` 生成四个彼此独立、
DirInfo 行与 v20 manifest 双重哈希绑定的原生 512x288 单事件产品：
`ac7114_001`、`ac7115_001`、`ac7115_013`、`ac7116_001`。每个均有
none/JA/ZH，合计 12 个 H.264/AAC 48kHz stereo MP4、57.466 秒唯一内容；
自动 QA 通过，但仍为 `human_playback_required` / `publishable=false`。
这些单事件不被表述为完整 natural family，也没有互相串联。

`ac7115_001` 的旧 manifest 对 request 9097、9090、9095 有可验证语音，却
没有独立字幕 cue。本轮使用官方 request code、OGG 名称、SHA-256、已解析
event-global 起点建立逐 request override，补入“！”、“！”和
“！…枫！”；没有统一目测平移。该事件现在有 8 条 voice-bound cue，需人工
重点检查三条补齐语音是否与张嘴／字幕同步。

增量审查根为
`bilibili_incremental_review_v43_event_exact_512_20260727`：U081-U084，
`01_REVIEW_STORY\batch_001`，4 个作品／12 个 exact MP4，全部为源文件的
同盘 hardlink；`00_UPLOAD_NOW` 与隔离媒体均为 0。none 目标
`BV1rUKN6iEcj`、JA 目标 `BV1zQKN6eEC6`、ZH 目标 `BV13bKN6nEsd` 已逐项
写入 `UPLOAD_INDEX.csv`，但人工批准前全部 HOLD。

总账推进到 `production_ledger_v12_20260727`：current production manifest
24→28，produced event 173→177，原先四条
`evidence_ready_event_waiting_route_product` 已全部转为
`produced_current_manifest_root`。全局指南推进到
`upload_guide_v43_20260727`：10 个已投稿、17 个可投稿、195 个待人工播放、
8 类明确排除，共 222 个精确文件。第一次未消费 v43 index 的指南草案已移动
到 `upload_guide_v43_20260727_superseded_missing_incremental_audit`，正式唯一
指南是无后缀的 v43 根；superseded 审计绝不上传。详细证据见
`docs/research/2026-07-27-event-exact-native512-checkpoint-v43.md`。

冻结交接根继续保持不变；P16/P17/P18、未闭合 child-local、互斥路线机械
串联和任何 upscale 继续 fail-closed。普通“待人工播放”不会停止无关产线。
当前 with-BGM 正式候选仍为 0；完成／精确阻断已发现 no-BGM 库存后再切换。

## 2026-07-27 生产冻结解除与原生 416 剩余素材审查 v42

项目所有者已明确解除同日生产冻结；已完成的
`bilibili_human_review_upload_freeze_20260727` 继续保持原样，不覆盖、不删改。
生产从 v10/v41 总账继续。只读穷尽核对确认当前没有新的、未生产且
event-exact 的原生 416 剧情 family／DirInfo 路线；因此本轮转入仍未覆盖的
17 个 evidence-ready 原生 416 玩法／素材事件。

本轮在
`material_collections_v42_native416_remaining_review_20260727` 形成四个
视觉-only 审查产品：ac0914 谣叙事转场、ac0914 五类十种结果、ac1103
出前胜利／复活背景与标志、ac2201 黑江瞄准玩法素材。共 38 个唯一片段、
147.563 秒，全部为原生 416x232、30fps、H.264、无音轨、无字幕；自动技术
QA 通过但仍是 `human_playback_required` / `review_only`。ac0914 结果的
20 个官方名称按 exact media 去重为 13 个画面并保留 7 个别名；ac1103
背景与标志合并为一个产品，避免两个成片重复认领相同事件。

增量审查根为
`bilibili_incremental_review_v42_native416_materials_20260727`。其中
U077-U080 各保留 none/JA/ZH 三个正确命名入口，共 12 个 MP4 入口、4 个
唯一 SHA-256；无音频／字幕差异的 sibling edition 均为同 inode hardlink，
`physical_duplicate=false`。`00_UPLOAD_NOW` 为 0，新文件只在
`02_REVIEW_MATERIAL\batch_001` 等待人工完整播放；none 未被省略。

总账推进到 `production_ledger_v11_20260727`：current material manifest
从 11 增至 15，覆盖事件从 105 增至 122，production-manifest
gameplay/effect `planned_unproduced` 从 303 降至 286。全局指南推进到
`upload_guide_v42_20260727`：10 个已投稿、17 个可投稿、183 个待人工播放、
8 类明确排除，共 210 个精确文件。详细记录见
`docs/research/2026-07-27-native416-remaining-material-checkpoint-v42.md`。

P16/P17/P18、未闭合 child-local、互斥分支机械串联和 superseded 继续
fail-closed。当前没有任何正式证据闭合的 with-BGM 渲染候选；BGM 来源身份
虽已部分闭合，但路线绑定、入口相位、循环与 fade/duck/stop 时间线仍阻断。
完成／精确阻断全部已发现 no-BGM 库存后，才正式切换 with-BGM。

## 2026-07-27 历史检查点：生产冻结与人工审查／上传交接

项目所有者当时冻结新增生产。本轮只把 `upload_guide_v41_20260726` 的精确文件
整理到耐久交接根
`bilibili_human_review_upload_freeze_20260727`，没有生成或重编码媒体，也没有
操作 Bilibili。交接包含 196 个命名 MP4 入口、194 个唯一 SHA-256：

- `00_UPLOAD_NOW`：17 个 exact-file 人工批准文件（15 ZH、2 JA、0 none）；
- `01_REVIEW_STORY`：59 个作品、168 个文件、6 批；
- `02_REVIEW_MATERIAL`：11 个作品、11 个文件、2 批；
- `03_QUARANTINED_DO_NOT_UPLOAD`：0 个 MP4，只保留排除说明。

全部 194 个唯一媒体通过同盘 NTFS hardlink 收录，无 copy fallback。ac4903
DirInfo row 8 的 none/JA/ZH 为一个合法跨目标 exact-hash 组：保留三个正确
命名入口，JA/ZH 作为 canonical none 的同 inode hardlink，并在
`ALIASES.csv`/`UPLOAD_INDEX.csv` 记录 `physical_duplicate=false` 和各自目标
BV。逐文件目标、分P名、追加/新建建议、自动 QA 与人工状态见
`manifests/START_HERE_UPLOAD_GUIDE.md` 和 `UPLOAD_INDEX.csv`。

独立复核确认 196/196 媒体哈希正确、8 个批次均不超过 10 个作品或约 30 分钟、
隔离项零泄漏。P16/P17/P18、superseded、旧错误/重复、10 个已投稿 exact hash
和未纳入 v41 的未闭合 child-local 项目均排除。详细记录见
`docs/research/2026-07-27-human-review-upload-freeze-handoff.md`。本检查点后停止
新增 family、渲染、逆向、BGM 和素材扩产；该冻结随后由项目所有者明确解除，
但本交接根继续作为不可改写的历史检查点保留。

## 2026-07-26 ac4904 原生 416 角色窗框 UI 素材审查 v41

本轮将 ac4904 的 15 个 SU/window 玩法事件按角色组整理为三片原生
416x232 视觉-only 素材：

- group 01：公共天线效果及环彩羽、八千代、二叶莎奈、鹤乃、菲莉希亚，
  16 段、55.666 秒，SHA-256
  `AB6500D70BD71BF2DE366DB11E6FADE39805D356AF89D3C92F2DF9D672138E0E`；
- group 02：鹿目圆、沙耶香、麻美、杏子、焰，15 段、48.000 秒，SHA-256
  `8A5868D05AB7B3E2C12CA5599AC68DE6996C67F805061C2EAE2B07D51C5CF628`；
- group 03：音梦、灯花、阿莉娜、环彩羽变体、忧，15 段、60.999 秒，
  SHA-256
  `76B1E742728B1948A0DB1FEDE89376630B70FF4EF35DC4E3D93DACCC00247593`。

耐久根为 `material_collections_v41_native416_ac4904_review_20260726`。
公共天线效果仅在第一片保留一次，后两片不重复；每名角色各含 intro、
additional、loop。三片 H.264 视频流直接复制，最终无音轨、无字幕，自动技术
QA 通过，但均为 `human_playback_required` / `review_only`。不消费 child-local
声音时序，也不声明 clean story 或原生 session。

总账推进到 `production_ledger_v10_20260726`：current material manifest
从 8 增至 11，覆盖事件从 90 增至 105，planned production-manifest
gameplay/material 项从 318 降至 303。`SUMMARY.json`、
`CURRENT_MATERIAL_COLLECTION_INDEX.json`、`SHA256SUMS.json` SHA-256
分别为
`0F29B74C717507F181CF67AE346350A8FBE1D9EEB86B223EC1B1DB3FF9B2B875`、
`3C48B7C22AC4CF413864370BCF0C1624CB1F9DFA3B0FD4B7EB1E0F57D968C2C5`、
`9A501C6DED8E78D2FF44E7D57CA8DF471F9E82DF527ED6D0783B1FBB3CDA4F78`。

逐文件上传指南推进到 `upload_guide_v41_20260726`，共 206 个精确文件：
10 个已投稿、17 个可投稿、179 个待人工播放、8 类明确排除。三片新文件均
以未来新建“MagiaReco Slot 原生416玩法／素材合集”BV 为目标；无字幕轨；
当前不追加、不替换。`UPLOAD_GUIDE.json`、`.md`、`.csv`、
`SHA256SUMS.json` SHA-256 分别为
`3E223C4A6718D4B7FA91C8BB7AED8AE52568F309A41DCA59BA8E987834761B70`、
`AD05FA5E82F3C28F965015D1A7CE7CA24F6C578055061A4A082830A9A8326116`、
`CD57600762E0FD4EDEE03DE19161A88B6CA4195C8F7C8E2FCFFD2E4A7DAB8922`、
`835B527362E8BC140A4082B7207C475163E331DDED014B7BCDF607EA00E08B42`。
P16/P17/P18 继续硬隔离；`ac7210_superseded_verbose_audit` 继续绝不上传。

## 2026-07-26 ac7204 原生 416 结果卡素材审查 v40

本轮按玩法语义把 ac7204 的 27 个原生 416x232 gameplay/result 事件整理为
两片视觉-only 素材：

- `ac7204_small_result_color_cards_v1__material_components__416x232_30-1.mp4`：
  小尺寸白／蓝／黄／绿／红／紫 intro+loop 共 12 段、12.000 秒，SHA-256
  `99631E653AA9A0756E32E9D2B29CE31DF8234FAE292285A901EA790E77EB0F5E`；
- `ac7204_large_result_color_cards_v1__material_components__416x232_30-1.mp4`：
  大尺寸六色加烟花、彩虹 intro+loop 共 16 段、16.000 秒，SHA-256
  `26828847F15CC76A2837ABCAD12D9C63EB88D59C0AE4647B572D76728D250D9F`。

耐久根为
`material_collections_v40_native416_ac7204_review_20260726`。两片 H.264
视频流直接复制，最终无音轨、无字幕；自动技术 QA 通过，但均为
`human_playback_required` / `review_only`。本批不消费 child-local 声音时序，
也不声明 clean story 或原生 session。

`ac7204_017/_021/_022/_023/_042/_043/_044` 的 parent DGM→child Z2D
event-global 时序仍未闭合，继续 blocked，没有被本批错误计入已完成。

总账推进到 `production_ledger_v9_20260726`：current material manifest 从 6
增至 8，覆盖事件从 63 增至 90，planned production-manifest
gameplay/material 项从 345 降至 318。`SUMMARY.json`、
`CURRENT_MATERIAL_COLLECTION_INDEX.json`、`SHA256SUMS.json` SHA-256
分别为
`9AE86965DDE7AB466BB442C0BE4B2FF2AAF972853EEABA6F289C11E76231581A`、
`B1A30C1C7829FC9169365C6DE7CE944DC52A38A351226F0AAC00A1AC59ACB854`、
`9F701DFD7616062ECA08679C0899F1745A7AACDF774221B6AA9F0B6D9392B185`。

逐文件上传指南推进到 `upload_guide_v40_20260726`，共 203 个精确文件：
10 个已投稿、17 个可投稿、176 个待人工播放、8 类明确排除。两片新文件的
目标均为未来新建“MagiaReco Slot 原生416玩法／素材合集”BV；建议分P名分别为
“小尺寸六色结果卡素材 ac7204”和“大尺寸六色与烟花彩虹结果卡素材 ac7204”；
当前不追加、不替换。`UPLOAD_GUIDE.json`、`.md`、`.csv`、
`SHA256SUMS.json` SHA-256 分别为
`34022B6A4D556A31C135F8AE230DD59F9FBE4B15B980961AE3EB713A370E7896`、
`7891A78A7FF7F3D93861A8E591D125A44FFE3621B3B18785D98FC97317F27537`、
`6002980A4B091A19DD6A6A15E31D19631E89EC7382FD28A57FC0DDC273E43B28`、
`D264B36CF8AC9E956AD957FB8D74CB369CEE7CF45A956C04F6CEE64E18932BDB`。
P16/P17/P18 继续硬隔离；`ac7210_superseded_verbose_audit` 继续绝不上传。

## 2026-07-26 ac0912 原生 416 小丘比引导素材审查 v39

本轮把 ac0912 的 42 个原生 416x232 小丘比三停引导／结果展示事件分流到一个
有限的视觉-only 玩法素材合集：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  material_collections_v39_native416_ac0912_review_20260726\
  ac0912_small_kyubey_3on_guides_v1\
  ac0912_small_kyubey_3on_guides_v1__material_components__416x232_30-1.mp4
```

成片 88.266 秒、416x232、30 fps，SHA-256
`B8C43A88E712BD11990C7D91C89E84C4D71E182E89C9AC3588CCD905E53862D6`。
计划绑定全部 42 个 v20 event manifest 与耐久 D: official-name video map；
公共小丘比、S 型五类结果、L 型五类结果按语义顺序排列。S/L flash 的两个官方
名字实际对应字节完全相同的 MP4，聚合 exact-AV 去重门禁保留两个 alias 而只
输出一次，因此 24 个计划名得到 23 个唯一片段。

H.264 视频流直接复制，最终无音轨、无字幕；本产品不消费也不声明 event manifest
中的 child-local 声音时序。自动技术 QA 通过，但 exact MP4 当前仍为
`human_playback_required` / `review_only`，人工确认前禁止投稿。它是玩法／素材
合集，不是 clean story，也不是一条原生 session。

总账推进到 `production_ledger_v8_20260726`：current material manifest 从 5
增至 6，覆盖事件从 21 增至 63，planned production-manifest
gameplay/material 项从 387 降至 345。`SUMMARY.json`、
`CURRENT_MATERIAL_COLLECTION_INDEX.json`、`SHA256SUMS.json` SHA-256
分别为
`828D8EFCC038972F5945A97AF150E6757930FCE4B50DBAC91E044F9F27DED0BC`、
`618E06CE83644CFF9B964CE04A7D8E1E41926986C20027FF9B40BE63EF4C7760`、
`AACE910EEAF1DD2AE7166209967865B3C66D7BCFFBBEAF4C2E4AF10592333F26`。

逐文件上传指南推进到 `upload_guide_v39_20260726`，共 201 个精确文件：
10 个已投稿、17 个可投稿、174 个待人工播放、8 类明确排除。本轮新增文件
只进入待审，目标是未来新建“MagiaReco Slot 原生416玩法／素材合集”BV，
建议分P名“小丘比三停引导与结果文字素材 ac0912”；当前不追加、不替换。
`UPLOAD_GUIDE.json`、`.md`、`.csv`、`SHA256SUMS.json` SHA-256 分别为
`700D9EB48B572D0B37A3CF538EE3553D64F9A70184D1C40C516EA1D35CB72945`、
`404F3E1DD77C4F6BD9C3E3EBEE94A39502C268B1F3C0A624E0278394D55289EE`、
`396BE82EBF6D0C67BB2353E221F1E0C3426F158638C3C4C5C2BB3EEE692691EC`、
`14FBC7DF3DBDEAD7F0E5FC672B89C8B5F239AE11AF821C4FB3B8A3E1C5E8126A`。
P16/P17/P18 继续硬隔离；`ac7210_superseded_verbose_audit` 继续绝不上传。

## 2026-07-26 原生 416 玩法 UI 素材审查 v38

继续按“416 路线／玩法优先于 512 TV 剧情”的顺序，本轮生成两片原生
416x232、30 fps、视觉-only 玩法 UI 素材：

- `ac8000_next_continue_ui_v1__material_components__416x232_30-1.mp4`：
  NEXT intro/loop 与继续 intro/loop 共 4 段、10.000 秒，SHA-256
  `9996E71365100D31E011109EFCAF2885B8A7818B9819D95A07016DD9C0276A89`；
- `ac8004_shutter_transitions_v1__material_components__416x232_30-1.mp4`：
  快门关闭 intro/loop 与失败开启共 3 段、2.333 秒，SHA-256
  `094CF75827BDDC4751086EA22EF82FC129137470C4D71B2A62F7D983689F8666`。

耐久审查根：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  material_collections_v38_native416_ui_review_20260726
```

两片 H.264 视频流直接复制，最终无音轨、无字幕；自动技术 QA 通过，但均为
`human_playback_required` / `review_only`，人工确认前禁止投稿。视觉合集不消费
也不声明 child-local 声音时序；尤其快门的外部老虎机声音没有并入本批。

总账推进到 `production_ledger_v7_20260726`：current material manifest 从 3
增至 5，覆盖事件从 17 增至 21，planned production-manifest gameplay/material
项从 391 降至 387；四部 v22 精确人工批准产品仍独立记录，当前 event manifest
风险标记不变。`SUMMARY.json`、`CURRENT_MATERIAL_COLLECTION_INDEX.json`、
`SHA256SUMS.json` SHA-256 分别为
`8C2C3CA25A714FA3392151D482345EC3FF3BC11C3F79C849F9D034098A675099`、
`727CD928883C2CF462558DCB223D520D6E161CFC77212F349D062279BAA75E1E`、
`246E80D363C1D9D6B0CC202BC123FC0DBB32FC56A805FC93F72151451EDCA4E7`。

逐文件上传指南推进到 `upload_guide_v38_20260726`，共 200 个精确文件：
10 个已投稿、17 个可投稿、173 个待人工播放、8 类明确排除。本轮新增两片
只进入待审，没有新增 READY。`UPLOAD_GUIDE.json`、`.md`、`.csv`、
`SHA256SUMS.json` SHA-256 分别为
`034911985AC003F3A9C7FE519A4844877FED7A463B611DA49F4938777E6AD1D5`、
`F172970838B25279A20CBC7B0DD55C3EA32F04DDCF5CD51BED717AA407750C24`、
`71A6B42765348A078C93FB0581D59D0747652346F88FCCE38010D752782E911C`、
`51BD737368C15E1210B57066521B691EE901FCB87112A771A47CA2A82E91AE6F`。
P16/P17/P18 继续硬隔离；`ac7210_superseded_verbose_audit` 继续只读且绝不上传。

## 2026-07-26 四部已人工批准章节恢复到投稿指南 v37

四个耐久 v22 中文章节的 MP4、SRT、chapter manifest、自动 QA 和 READY hash
已重新对照项目所有者的精确播放批准记录。它们现在恢复为可投稿 exact files：

- `ac1102_full_no_bgm_zh_review_v1.mp4`，原生 416x232，建议分P
  “菲莉希亚牧场完整章节（含已验证效果） ac1102”，SHA-256
  `F2236AC4B3235C645E7408539E37AF2422077D8300C9EED2339CE73E15561BD2`；
- `ac1103_full_no_bgm_zh_review_v1.mp4`，原生 416x232，建议分P
  “鹤乃外送修行完整章节（含胜利效果） ac1103”，SHA-256
  `C1789C88415FEE6F52A4702B62A2F79ABB5877BAC55BE4681F56E27AC2BE5B1C`；
- `ac1104_full_no_bgm_zh_review_v1.mp4`，原生 416x232，建议分P
  “海滩香蕉船完整章节（含已验证效果） ac1104”，SHA-256
  `44CB183FE70CB384995582453D76F06F2CEFD95216D888245566D961AAA51053`；
- `ac5208_full_no_bgm_zh_review_v1.mp4`，原生 512x288，建议分P
  “三组魔法少女追击攻击 clean story ac5208”，SHA-256
  `55875D4C661B2A6A5FEC077A2D3235C04AF98DC264DA104A2258C29E7392626D`。

批准只绑定这四个具体 ZH MP4，不外推到 none/JA、单事件拆片或重渲染。
前三片建议新建或追加到“原生416完整章节（含已验证玩法效果）”BV；ac5208
追加到 clean-story 中文章节 BV。Codex 不上传。

`ac1103_013` 单独三版生产在预检阶段 fail-closed：官方 req4058 和 req4059
是两段相邻语音，但运行时只显示一条合并字幕；当前构建器仍是一条 cue 绑定一个
request ID。req1086 CLEAR 基础声音也尚缺单独的 hash-bound scene-SE 角色覆盖。
禁止把 req4059 假标为 SE 绕过门禁，因此本轮没有生成 standalone none/JA/ZH；
现有整章 ZH 的精确批准不受影响。

穷尽式总账推进到：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  production_ledger_v6_20260726
```

新增 4 个 exact owner-approved legacy product、覆盖 40 个唯一 event
occurrence 的独立索引；它只记录具体成片覆盖，不反向清除当前 v20 event manifest
的 child-local 风险，也不批准 sibling editions。
`OWNER_APPROVED_LEGACY_PRODUCT_INDEX.json`、`SUMMARY.json`、
`SHA256SUMS.json` SHA-256 分别为
`ED6CCAFD1865E920231DBA603C71ED25B0B17DD07FA6FE84D3988D67CD70E45D`、
`9D2C5F32DFFA3C0E15A8C7763CA45CBFB5D9B92F517486715B8EF7093612C91A`、
`EBB6CDE07E3DE840C73FF9FA356F69EB03EAECCCD787AF281765C9563863AA6A`。

逐文件上传指南推进到：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  upload_guide_v37_20260726
```

共 198 个精确文件：10 个已投稿、17 个可投稿、171 个待人工播放、8 类明确
排除。本检查点新增加的 READY 仅为上述四个 exact ZH。
`UPLOAD_GUIDE.json`、`.md`、`.csv`、`SHA256SUMS.json` SHA-256 分别为
`4104818D650A94A982F4FB04EADABF1E755AF624EE1F6D3CE9072BBEAFB4170D`、
`7A968BF1022496619FF95195707BF970D5A218FE67F401E14E6A5E627371E37B`、
`73E486329647E8F2FDCAE81772810D6CFD130D86E3533C66767D967D13895FD5`、
`0C2A72972A1B48E29805DDAAFFB47B7359F77684ABD755C58666974CD5392F6F`。
P16/P17/P18 继续硬隔离；`ac7210_superseded_verbose_audit` 继续只读审计且
绝不上传。

## 2026-07-26 原生 416 视觉素材审查批次 v36

在当前证据成熟的原生 416x232 clean-story 路线扩展完成后，本轮把三个有限
视觉组正式分入玩法／素材审查产品，不把它们冒充自然剧情，也不以自动技术
检查代替人工批准。耐久输出根为：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  material_collections_v36_native416_review_20260726
```

共 3 个 MP4：

- `ac0906_small_kyubey_actions_v1`：6 段，15.333 秒，SHA-256
  `248E3C6A1A7ADB5564A02E1D0AB161636FDFBD5C2D5FD98CE6CA030064A0A8E6`；
- `ac0931_uwasa_battle_intros_v1`：5 段，105.000 秒，SHA-256
  `BCB19F3C3C5B14070DCE0C5153C125A71EB67E0B9899D662A9360B88F783294D`；
- `ac5004_chance_color_titles_v1`：7 段，34.000 秒，SHA-256
  `C8728053A829D1FC89CB20B3EC3B88C6084B4053433CCCF7041C4686381D14AE`。

三片均保持原生 416x232、30 fps，H.264 视频流直接复制，最终有意无音轨、
无字幕。自动技术 QA 通过，但状态全部为 `human_playback_required` /
`review_only`，当前禁止投稿。ac0931 的一个源片带 ALAC 音轨；视觉素材合同
明确丢弃所有源音轨，manifest 同时保留逐源音频签名，最终 QA 验证成片只有
视频流。

穷尽式总账已推进到：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  production_ledger_v5_20260726
```

它通过 hash-bound base plan 继承 v4，只新增 v36 material root；记录 24 个
current production manifest、3 个 current material manifest、173 个已产
audience event、17 个已产 material event 和 62 条已产 DirInfo route。
剩余 planned gameplay/material 项从 408 降至 391，不改变剧情 READY 状态。
`ac7210_superseded_verbose_audit` 已显式排除，正式唯一来源仍为 v30
`ac7210`。`SUMMARY.json`、`SHA256SUMS.json` SHA-256 分别为
`7BC3C52490C849512A11D93B876F18268A5768984B113ED2BA9804D60D95C72C`、
`9BF7647370C4BD50D6B1068568B3F04818FD0D7DAA5799D8EF297D495C8435D8`。

本检查点逐文件上传指南：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  upload_guide_v36_20260726
```

共 194 个精确文件：10 个已投稿、13 个可投稿、171 个待人工播放，以及 8 类
明确排除。v36 三片的目标是未来新建“MagiaReco Slot 原生 416 玩法／素材
合集”BV；当前既不追加也不替换，且没有字幕轨。`UPLOAD_GUIDE.json`、`.md`、
`.csv`、`SHA256SUMS.json` SHA-256 分别为
`AA072277B54C0D26907990175410941BE83ABE9B6F91804DC0DE07D91A42A0F2`、
`08EEC6972F3FDD24610E71B66EE4F6FEF4A7132217B56BD58652F59FCDAC9278`、
`7C28A2BFF2C966E2E603D9837E6E7EB522D166991F133C674462C43A984EB7A6`、
`02E4C9591E5D57212BA002973B7DE8644153F1D771A94BAB6CD0F3EF6D9FBA45`。
P16/P17/P18 继续硬隔离；Codex 不上传。

## 2026-07-26 P11/ac0911 九条路线与章节长版 v35

DirInfo kind 36 共 14 条路线。本轮从当前 v24 ac0911 family master 中生成
rows 0–7、9 的九条独立原生 416x232 路线，并保留一个明确标注为
`edited_route_chapter_showcase_not_single_native_session` 的九章节长版。
每个产品均有 none/JA/ZH，总计 10 个内容产品、30 个 MP4：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  no_bgm_editions_v35_ac0911_mature_routes_20260726\ac0911
```

rows 8、10、11、12、13 已 fail-closed 排除：row 8 的 `ac0911_007`
缺当前现代 event manifest 且不在 source family；其余四条终点
`ac0911_013/_016/_014/_015` 不在当前 audience catalog 或 source family，
禁止猜测补入。旧 P11 具体 ZH 文件已由项目所有者投稿且保持只读；其人工批准
不外推到本轮 30 个 exact outputs。

自动 QA 为 9/9 路线完成、0 failure，确认 DirInfo 完整分区、来源 master/hash、
原生 416x232、30 fps、H.264/AAC 48 kHz stereo、无 upscale、字幕回读和同产品
none/JA/ZH 音频包及解码 PCM 一致。`BATCH_MANIFEST.json`、
`AUTOMATED_QA.json` SHA-256 分别为
`86136C5611B3169D830C22A103057DEA46E7A03AB54D49D719C925F5D2DFC31F`、
`7B635566FB268C6D68C1D3676F09EA1B10DFA240C0EFEC0EE031CAD6C653FFDD`。
30 个文件全部必须先人工播放，当前禁止投稿。

穷尽式总账已推进至：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  production_ledger_v4_20260726
```

它记录 24 个 current manifest、173 个已产 audience event、62 条已产
DirInfo route，并把 ac0911 的五条阻断路线显式列入 excluded。`SUMMARY.json`
和 `SHA256SUMS.json` SHA-256 分别为
`8CE13680052442C90E7F4BE4CD0BA2F4198A8402D69457865677114986E18A3E`、
`106935BC88CEA249EBBC76D10B884D7B41B16C6D1C0AEDD5D09B26E1EF516AFB`。

本检查点逐文件上传指南：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  upload_guide_v35_20260726
```

共 191 个精确文件：10 个已投稿且禁止重复、13 个可投稿、168 个待人工播放，
以及 8 类明确排除。新增 30 个 ac0911 文件全部为
`human_playback_required`。`UPLOAD_GUIDE.json`、`.md`、`.csv` SHA-256
分别为
`669FA2A1D44EC4D06248D0253962592A9090DC9DC2AA69A54F98556FE602E36F`、
`9D7EECAFA235ABBE33885F3F7B4F1EDC117A464796CB2819B2028DC6C2CF0D4F`、
`5CA04032FA474229DE44D9D34B6D99D9C3504455643B8CD5ADD229E42BC05AFB`。
P16/P17/P18 继续硬隔离；Codex 不上传。

## 2026-07-26 P19/ac6007 完整入口有限候选、总账 v3 与上传指南 v34

P19/ac6007 的 DirInfo kind 174 已按当前静态证据完整分流。rows 0/1 是两条
互斥的原生 416x232 clean-story 路线：

```text
row 0: ac6007_001 → ac6007_002 → ac6007_003 → ac6007_004
row 1: ac6007_001 → ac6007_005 → ac6007_006 → ac6007_004
```

入口 `ac6007_001` 不是五个 component 的线性串接。父级 presentation interval
证明底层场景从 0 开始；1.200 秒后由不透明标题层接管。候选因此使用
`lev_c001_MR` 36 帧后接 `AT_kuma_title` 77 帧和标题 loop 90 帧，共
203 帧／6.767 秒；同一时段的 `lev_c002/c002_LP` 仅是被标题遮挡的下层，
没有机械接到片尾。缺失的 `title_add/title_add_LP` 明确作为效果层排除。
request 1034 和 2192 两条 direct-parent 场景 SE 均从 event-global 0 开始，
并允许尾音跨入下一事件。

本轮在以下 D: 耐久根生成两路线 x none/JA/ZH 共 6 个 MP4：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  manual_review_candidates_v34_p19_ac6007_complete_routes_20260726\ac6007
```

`BATCH_MANIFEST.json`、`AUTOMATED_QA.json` 的 SHA-256 分别为
`16C639C62688AE3570FB01EFE48E39861B64E87E3692DB213B6C9676B0E8380E`、
`D9149F5CCDA81B55358CC303315067E2123191DAA4DE460CF5D39A405D7EDBDB`。
6 个文件规格 QA 全部通过，但 exact file 尚未人工播放批准，禁止投稿。重点
复看 0–10 秒、1.200 秒标题切换、6.767 秒入口到分支边界，以及全片张嘴、
语音、字幕和场景音。旧 P19 已投稿 ZH 文件保持不变。

rows 2/3/4 终止于或全部由 320x256／512x416 component-only 玩法效果构成，
只进入玩法／效果合集，不混入干净剧情。

穷尽式总账已推进到：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  production_ledger_v3_20260726
```

当前计入 173 个已产 audience event、53 条已产 DirInfo route、23 个 current
manifest；`ac7210_superseded_verbose_audit` 仍只在 superseded 审计索引中。
`SUMMARY.json` 与 `SHA256SUMS.json` SHA-256 分别为
`2555DAE4E587E390D19593A00E65184B096D3B3E346E4CDB46E97BBEFCA7F366`、
`420F3C69026622212C008FDC4F794EBAE657E180D4CEE19AB80D46F8BED38B96`。

本检查点逐文件上传指南位于：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  upload_guide_v34_20260726
```

它包含 161 个精确文件：10 个已投稿且禁止重复、13 个目前可投稿、138 个
必须先人工播放；另有 7 类明确排除。新增 6 个 ac6007 文件全部属于
`human_playback_required`，没有扩大批准范围。`UPLOAD_GUIDE.json`、
`UPLOAD_GUIDE.md`、`UPLOAD_GUIDE.csv` 的 SHA-256 分别为
`BD9E16B9C2EFA7C71D6791F2E68D1429F5F91F5D9032C0DE2F0C71820DD4252C`、
`ABC1C2B8A5046CA9B237C691E20B4136C973AF95757EE7EB5B02ABE596E66CCB`、
`D35BF47B7674BF5561030265B841FB6F7620965D1F7193A2A41A770788FA29A3`。
P16/P17/P18 继续硬隔离；Codex 不执行上传。

## 2026-07-26 原生 416 路线量产、穷尽式总账 v2 与上传指南

本检查点继续以原生 416x232 路线为最高优先级，没有新增 512 系生产，也没有
upscale。v30–v33 当前共包含 47 个内容产品、141 个最终
none/JA/ZH MP4：

- v30：ac0908 六条强入口独立路线加一个明确标注的跨路线参考合集，以及
  ac7210 DirInfo rows 0/1，共 27 个 MP4；
- v31：ac4902 五条去重路线加编辑章节合集、ac7206 六条路线加编辑章节合集，
  共 39 个 MP4；
- v32：ac0908 DirInfo rows 6–11 的六条完整 `001 → 菜品 → 008`
  独立路线，共 18 个 MP4。每条入口固定使用已批准的 187 帧饭店外景／侧身炒菜
  presentation，并保留其已批准的跨 outcome 边界场景声；
- v33：ac4903 DirInfo kind 114 的 19 条独立 clean-story 路线，共 57 个
  MP4。预检纠正了“简单入口段无音频”的旧摘要：`001/007/008/016/018`
  各有一条 event-global 0 的 direct-parent 场景 SE，成片保留这些 SE 及其
  跨下一事件边界的尾音。rows 14/18/21 因 `ac4903_015` 混合 416x232
  剧情与 256x144 胜利／玩法效果，继续排除到分层效果合成。

v32 manifest、QA 的 SHA-256 分别为
`FDD86EE89E0FC6F2DB6A9AD88D6404BF4011B62FFCBC589BE5EACDA89429A1CC`、
`1F257C92043EEF9307E7567191E3F64F995EBEAADB16C4538A015C0993397533`；
v33 manifest、QA 分别为
`64BE46ADB85DC7D8B776FF5B6069492411E43AB909F2947F3EBEF628A0720877`、
`BFB4B0A927754BF69F5303D4BAF802DAA1233653617032BD0DF05450F000210C`。
v32/v33 的新输出均仅有自动 QA，通过不等于人工播放或投稿批准。

穷尽式总账现位于：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  production_ledger_v2_20260726
```

母集为 7,753 个 audience event、926 个当前 production-manifest event、
13,558 条 DirInfo route 与 5,508 条 component/mixed review row。当前计入
172 个已产 audience event 和 51 条已产 DirInfo route；其余逐项归入 blocked、
玩法／效果合集或素材合集。`ac7210_superseded_verbose_audit` 已从 current
扫描显式排除，只在 `SUPERSEDED_AUDIT_INDEX.json` 中作为历史审计保留，永不
上传；正式 ac7210 只把 rows 0/1 计为已产，rows 2/3/4 明确阻断。
`SUMMARY.json`、`SHA256SUMS.json` 的 SHA-256 分别为
`602C8099A81562577BB27CF5B6503E037F21F9BACC2372A15B0280F67F1AC0C7`、
`8C0CDB85C5E7829229BB328C00E7F03D2618022B2BB661EE3A7274C1CE5E0C74`。

每个后续生产检查点必须同时生成逐文件上传指南。本轮指南位于：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  upload_guide_v33_20260726
```

它逐项记录目标 BV／字幕轨、绝对文件夹、精确文件名、SHA-256、建议分P名、
追加或替换动作、自动 QA、人工批准和排除项。当前共 155 个精确文件条目：
10 个已投稿且禁止重复、13 个 exact-file 可投稿、132 个必须先人工播放，
另有 6 类明确排除。13 个可投稿文件中，当前 ZH 轨为 P12、P23、ac0908
六条强入口路线、ac0908 单独的 reference-derived 参考合集、ac7210 rows 0/1，
另有 P12/P23 两个已人工确认的 JA 文件；Codex 不执行上传。P16/ac6003、
P17/ac6004、P18/ac6005 继续全 family 硬隔离，不得因其他 family 量产成功而
重新进入投稿清单。`UPLOAD_GUIDE.json`、`UPLOAD_GUIDE.md`、
`UPLOAD_GUIDE.csv` 的 SHA-256 分别为
`1C9951072EEE457E5F43432CDB804C7C1F15D9D3B0B1A1F9988071A853B1352B`、
`FFD5CB23D1BEB4C35A3B489BCD391045519D71B966A706FA717768AE5B45FD34`、
`D491ECF3960A49F42B424018196B984489ED1FC82ECCEFADF35C6AD702DD023D`。

Frida 运行时环境前提仍以
`D:\magia\MyProducts\casino\runtime_recovery_20260725\
RUNTIME_RECOVERY_FRIDA_17_16_4.md` 为准：17.5.2 zygote agent 污染已通过
完整 reboot 清除，host/server/ARM64 Gadget 统一到 17.16.4；禁止枚举、
spawn、zygote attach、双 27043 session 与宽泛 observer。P16 仍只允许在真实
slot 画面后用 ADB numeric PID 做单 session 轻量定向 probe，且该阻断不影响
纯本地量产。

更完整的生产边界和目录清单见
`docs/research/2026-07-26-exhaustive-416-production-checkpoint-v33.md`。

## 2026-07-25 晚间人工状态、入口遗漏审计与 416 路线补全

项目所有者已确认此前批准的 P11、P13、P14、P15、P19、P20、P21、P22、
P24、P25 共 10 个**具体 ZH MP4**已经由本人投稿。精确文件与 SHA-256 记录在
`owner_attestations/owner_uploaded_10zh_20260725.json`；这不扩展到 none/JA，
Codex 没有执行上传，也不会覆盖已投稿文件。

最新人工播放状态按具体文件绑定：

- P12 最新去重路线候选 JA/ZH 与 P23 身份纠正候选 JA/ZH 均已确认可用；
- ac0908 DirInfo rows 52–57 的六个具体 ZH 路线分段，语音与字幕时序已确认正常；
  none/JA 没有自动获得批准，此批准也不外推到其他 child-local 事件；
- P17 none/JA/ZH 继续隔离：除 6 条 child-local 起点未闭合外，
  `ac6004_006` 还漏掉 request 3260 的整条 7.899 秒对白；
- P18 CU 成功候选 none/JA/ZH 继续隔离：嘴动时无声／无字幕，声音与字幕又在
  对应嘴动前出现，并且疑似漏对白。

精确哈希与边界分别记录在
`owner_playback_approved_p12_p23_ac0908_20260725.json` 和
`owner_reconfirmed_quarantine_p17_p18_20260725.json`。

ac0908 与参考片顺序不同的原因已经闭合：v27 只实现 DirInfo kind 33
rows 52–57 的强火入口子路线 `009 → 单一菜品 → 008`；参考片是跨互斥路线的
编辑合集，另含弱火入口 `ac0908_001`，其同一父事件内先播放饭店外景
`c01_MR`，再播放侧身炒菜 `c02`。现已生成一个仅含 ZH 的原生 416x232 补全
审查片：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  manual_review_candidates_v28_ac0908_complete_showcase_zh_20260725\
  REVIEW_NOW_1_MP4
```

成片顺序为
`001 → 002 → 001 → 003 → 001 → 004 → 009 → 006 → 009 → 005 →
009 → 007 → 008`，2,745 帧、91.500 秒，H.264/AAC 48 kHz stereo。
MP4 SHA-256 为
`53C0A918C043F78D8CB70DC643747C7DEC3FC45D5FA107A91251A347586AFD51`。
清单与自动 QA 已改用版本根内相对路径；`SHOWCASE_MANIFEST.json`、
`AUTOMATED_QA.json` 和审查目录 `MANIFEST_SHA256.json` 的 SHA-256 分别为
`F77FFFF0674D41DAC7CFC9A7357EA8DF6B4C1FB9A2152E2261E7FD631DF05C4B`、
`04F47F309D0CBB425F1C62DD4A81F46FED2AB96EB1CF44605D31125C9F53DEA6`、
`3FAC6584AB661542A843C02A9FFB4731F39B3F2C1BB294ABA8816905EBFDCB52`。
参考片只作为顺序和入口呈现时长证据，未取用其像素或音频。该片明确是
`reference-derived all-outcomes showcase`，不是一次原生游戏 session，当前仍
`HUMAN_REVIEW_REQUIRED`；原六个 ZH 路线分段继续保留。

对现有 audience 长产品的有限入口审计还确认 4 个已投稿 ZH 存在 A 类公共入口或
连接段遗漏／路线扁平化：P13 `ac4903`、P19 `ac6007`、P24 `ac7206`、
P25 `ac7210`。这不否定已投稿文件的片内播放批准，只说明它们不能代表完整自然
family。风险表在
`series_proposals/audience_entry_route_scope_audit_20260725.json`，严格区分：
A 公共必经遗漏、B 互斥路线另产、C 玩法／外框／组件另集。

其中 P25 已先补两条独立 416 路线：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  manual_review_candidates_v29_p25_ac7210_route_supplements_zh_20260725\
  REVIEW_NOW_2_MP4
```

- row 0：`001 → 002 → 003 → 004`，924 帧、30.800 秒，
  SHA-256 `8927CFDF7497B63B4FA47D7D9DB0C340FC837596547F3B9F4E8E15C764079088`；
- row 1：`001 → 005 → 003 → 004`，1,121 帧、37.366667 秒，
  SHA-256 `990407DD95ABC18911782AFA9F2EC7AA3E2F17997BA9F716892D1AFFB1A06849`。

`SUPPLEMENT_MANIFEST.json` 与审查目录 `MANIFEST_SHA256.json` 的 SHA-256
分别为
`3BE75ADC29B257D1678EE0CE7FECCB7EA1AA89404FFB014AA710A5A9BF5DCE5E`、
`0097F0456CFAE9F59871A059904AAA8C2B84498318FDDA155F4B72B16F108EF0`。

`_002/_003` 的父 EventInfo 场景声分别长于静态视觉，缺少同-run 下一事件启动
边界；候选按声音尾部保持最后一帧，故标为
`PRESENTATION_BOUNDARY_RISK_HUMAN_REVIEW_REQUIRED`，不得直接投稿。
P13/P24/P19/P12 的后续补全依证据成熟度继续，不能机械串入一部自然播放。

## 2026-07-25 人工播放纠错与上下文迁移

最新、完整的接手说明位于：

```text
docs/HANDOFF_CODEX_2026-07-25.md
```

项目所有者已明确 `黑羽 / 黒羽`、`黑 / 黒`、`黑江 / 黒江` 是三个不同身份。
旧声源标签 `speaker_code=kuro` 具有上下文歧义，禁止全局映射：P12 `ac4902`
两次 `くそっ！` 是黑羽；P23 `ac7117` 白衣奔跑喘息者是黑；`kuroe` 是黑江。
工具现改用 event + request + code name + audio SHA-256 的精确身份覆盖，未列出的
歧义 `kuro` 不自动加角色名前缀。

本轮纠错候选最初为 7 个 MP4；P18 人工播放失败后，当前审查入口已收束为
P12/P23 共 4 个 MP4：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  manual_review_candidates_v26_corrections_20260725\REVIEW_NOW_4_MP4
```

- P12：去重、route-aware 的 JA/ZH 两版，24 个唯一 occurrence、330.733 秒；
  `ac4902_003/_059` request 8340 两句只按已授权证据显示黑羽；
- P18：DirInfo 只证明 `010 → 013 → 014` 是 CU 成功路线，未证明现有静态
  composition 的声音与画面全局时间。项目所有者播放后确认三版均失败：语音与嘴型
  不符、角色间声音时序和字幕时序错误，并疑似漏对白；三版已 fail-closed 隔离；
- P23：JA/ZH 两版，146.033 秒；只对授权的 9634/9635/9638/9663 标注黑，
  `kuroe` 仍为黑江，标题候选为“黑江与黑的相遇 ac7117”。

P12/P23 自动 QA 通过，且上述四个**具体最新文件**现已获人工播放可用确认；
批准不扩展到旧版或其他 edition。自动规格 QA 未能发现 P18 的语义时序错误，
不能覆盖人工播放否决。P12/P18/P23 旧版与尚未修复的 P16 旧版共 12 个
none/JA/ZH MP4 已全部移出活跃投稿目录，保存在
`quarantine_pending_fix_20260725`。项目所有者随后人工否决 P17 `ac6004`：
角色嘴型与语音／字幕严重错位，共用风险时间线的 none/JA/ZH 三版已移至
`quarantine_human_playback_failed_p17_20260725`。上传准备根现在只保留 10 个
family、30 个 MP4；明确清单见 `UPLOAD_NOW_STATUS_20260725.md`。

P17 根因已经闭合为证据层级错误，而非编码随机漂移：长片顺序为
`005 → 006 → 008 → 011 → 012`；仅 request 3265 有 resolved runtime timing。
其余 6 个对白起点只有 child Z2D callback 局部时点，旧管线还因父级播放起点未
解析而整条漏掉 `_006` 的 request 3260（官方语音 7.899 秒）。因此禁止按肉眼
统一平移；修复必须校验 expected request set，并逐 request／逐 child Z2D 绑定
hash-bound parent offset。production manifest builder 现对此 fail-closed：
缺 resolved runtime event manifest 或父子实例化偏移时，
`event_global_z2d_timing_ready=false`、`render_ready=false`。

项目所有者已完整确认并由本人投稿其中 10 个具体 ZH 文件：P11、P13、P14、P15、
P19、P20、P21、P22、P24、P25。精确文件名与 SHA-256 位于
`audit\HUMAN_PLAYBACK_APPROVALS_ZH_20260725.json`，文件 SHA-256 为
`62B9E9EC7B0BC65AE3D4F23298C1A547FE5215FEDB0F473E9597C275531D514C`。
此批准不扩展到未观看的 none/JA。

项目所有者另报告 P16 `ac6003` 约 47 秒起语音领先画面、P18 `ac6005` 缺少彩羽
扑向灯花和音梦的 512x416 后半故事，并质疑若干线性 family 的完全重复或分支
机械串接。本轮新增面向观众产品的 exact AV+subtitle duplicate fail-closed 门禁；
现有 267 个事件 occurrence 中确认 26 个完全重复，去重可减少 389.500 秒，但
原始单事件档案全部保留。

P18 被否决的三版另位于
`manual_review_candidates_v26_corrections_20260725\
QUARANTINE_REJECTED_P18_20260725`；`REJECTION_STATUS.json` SHA-256 为
`35BC5419986A5A2D45478E731E7260022BD428E260C7F0D7675C29F166CD5736`。

P16 当前继续隔离且没有修复候选。`ac6003_009` request 5843 的身份正确，但仍缺父
DGM 到子 Z2D 的事件全局实例化偏移，禁止根据 467 ms 片头猜值。2026-07-25 的
运行时故障已由 tombstone 定位为 device frida-server 17.5.2 注入 zygote64/32 后，
子进程在继承的 `/memfd:frida-agent-64.so` 内 fault；另一次 Gadget 又在真实 slot
主画面出现前过早注入。运行时现已恢复为统一 Frida 17.16.4，zygote 清洁，且真实
slot 画面上的 numeric-PID Gadget attach 已验证；P16 仍只允许一次单 session
轻量父 DGM→子 Z2D probe，禁止进程枚举和宽泛 observer。恢复记录：
`D:\magia\MyProducts\casino\runtime_recovery_20260725\
RUNTIME_RECOVERY_FRIDA_17_16_4.md`，SHA-256
`3B62A80DA4C26D4CB5EF2D1CB8D128DB41CC8E75C810C1C094C79D5272A03880`。

项目所有者最新调整产品优先级：以“菲莉希亚牧场”同类的原生 416x232
老虎机动画／选项路线为核心，停止新增 512 尺寸生产。`ac7101–ac7107` 暂停。
ac0908 已按 DirInfo kind 33 rows 52–57 建立六条独立路线，每条保持
`009 → 单一菜品选项 → 008`，共完成 none/JA/ZH 18 个审查 MP4。旧规格自动 QA
全部通过，但后续只读审计确认 `_002` 至 `_009` 都没有 resolved runtime event
manifest 或父 DGM→子 Z2D 的事件全局实例化偏移；全部对白仍只是 child-local
callback 时点。因此 18 个文件现为 timing-risk 有限人工候选，不是 READY 或量产
成功。六个具体 ZH 文件的语音／字幕时序现已获项目所有者播放确认；none/JA
仍未批准，且逻辑上的 parent-offset 风险没有因此外推闭合。
审查入口：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  manual_review_candidates_v27_ac0908_option_routes_20260725\
  REVIEW_NOW_18_MP4
```

审查目录 `MANIFEST_SHA256.json` SHA-256 为
`8DD03A8D8C7EFBEDC515F0EB7D78F8B1BC80CDD61449210B2D643F6007D079AF`；
根目录 `TIMING_RISK_STATUS.json` SHA-256 为
`91D44761921497807FE253D577D3C578D63A37B203AE49865AC10E36609C1950`。

范围审计还发现 v24 曾有 93 个事件使用相同 child-local 证据获 READY，其中
63 个为 416x232。这只是待重验风险清单，不等于 93 个成片全部已观察到错误；
以后量产必须先经过新 fail-closed 门禁。

未来 416 产品合同以 ac1102 同类“保留自然分段的 family 长片”为首选。
ac0908 当前是 6 条路线 × none/JA/ZH 3 edition = 18 个文件，不是 18 部内容；
六条 ZH 路线分段已通过人工时序观看，并已保留。另行生成的 v28“六种菜品入口
补全参考合集”仍需单独观看，不能从分段批准自动晋升。

## 2026-07-24 系统重装恢复与 no-BGM 全面扩产

项目所有者已把此前通过播放审查的内容正式投产到 Bilibili，并手工完成分 P 分类与
命名。当前三个公开 edition 及页面标题为：

- `BV13bKN6nEsd`：`魔法纪录 街机版 动画整合 无BGM中文版｜游戏资源解包与技术还原`
- `BV1zQKN6eEC6`：`魔法纪录 街机版 动画整合 无BGM原始日文官方字幕版｜游戏资源解包与技术还原`
- `BV1rUKN6iEcj`：`魔法纪录 街机版 动画整合 无BGM无字幕版｜游戏资源解包与技术还原`

后续投稿准备可以沿用这一 edition 级标题格式和项目所有者的分 P 命名风格，但不得
仅根据 `ac` 编号虚构剧情标题。两项既有投稿也不自动构成对新 v24/v25 输出的逐部
人工批准。

系统重装后已经直接核验 Python 3.14.6、Git 2.55.0.windows.3、GitHub CLI 2.96.0；
本轮恢复 FFmpeg 8.1.2 full build、Node.js LTS 24.18.0、npm 11.16.0、
Frida 17.16.4、frida-tools 14.10.4，以及 `requirements.txt` 的 requests 2.34.2、
tqdm 4.69.0、mitmproxy 12.2.3、fonttools 4.63.0。FFmpeg/ffprobe 位于
`C:\Users\proje\AppData\Local\Microsoft\WinGet\Links`，Node 位于
`C:\Program Files\nodejs`；旧终端看不到新 PATH 时必须显式使用这些路径或重新开
终端。

v24 耐久输出根：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  no_bgm_editions_v24_mass_20260724
```

`ac0911/ac4903/ac5203/ac5301/ac5303/ac6003/ac6004/ac6005/ac6007/ac7206/ac7210`
共 11 个 family、95 个 event、111 条对白、116 个 scene SE、22,308 帧、
743.599 秒及 33 个 none/JA/ZH MP4，全部通过当前 family 和 aggregate 自动 QA。
八个 family 保持 416x232，三个保持 512x288；全体为 30/1 fps、H.264、AAC
48 kHz stereo，无 upscale、无插入黑场、无 BGM layer、无 unresolved audio。

旧 v23 `ac5203_full_no_bgm_editions_v1` 虽通过媒体流 QA，但遗漏
`ac5203_2_001` request 7856 的 `負けるもんか！`，同时错误携入 chance-button
presentation text，已列入 `invalidated_output_roots.json`。权威 v24 重建位于
`batch02_ac5203_ac6005`，含 7 event、7 个 reviewed dialogue cue、14 个
evidence-bound audio layer、1,216 帧、40.533 秒，三版均通过。

v25 耐久输出根：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  no_bgm_editions_v25_next_story_20260724
```

- `ac4902`：46 event、46 cue、98 audio layer、20,708 帧、690.267 秒、416x232；
- `ac7117`：11 event、32 cue、43 audio layer、4,381 帧、146.033 秒、512x288；
- `ac7112`：14 event、45 cue、59 audio layer、5,916 帧、197.200 秒、512x288。
- `ac7113_main_512x288`：9 event、32 cue、41 audio layer、3,948 帧、
  131.600 秒、512x288；
- `ac7113_opening_512x416`：1 event、2 cue、3 audio layer、342 帧、
  11.400 秒、512x416。

五组共 81 event、157 cue、35,295 帧、1,176.500 秒及 15 个 edition MP4，全部
通过同一 native-size/frame/sample/source/subtitle/audio-role 门禁。v24+v25 的
权威 aggregate audit 位于：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  no_bgm_aggregate_audits_20260724\
  final_audit_v24_v25_strict_media_20260724_230000\aggregate_audit.json
```

它整体通过 16 family、176 event、48 MP4、268 条对白、57,603 帧和
1,920.099 秒；471 个音频层为 268 voice + 203 scene SE，未解析音频为 0。
尺寸分布为 9 个 416x232、6 个 512x288、1 个 512x416。此次严格重跑还逐份解析
JA/ZH SRT，并独立重算 audio master 与三版 MP4 的 AAC packet hash、
presentation timeline、精确 decoded sample 数和 PCM hash。

供项目所有者手动投稿的 NTFS 硬链接包位于：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  bilibili_upload_ready_v25_no_bgm_20260724_16families
```

其中 `zh/ja/none` 已按 P11-P25 排列；三个
`replace_old_p10_ac5203` 子目录单列正确的 P10 替换文件。45 个 P11-P25 新增投稿
链接和 3 个 P10 替换链接（合计对应 aggregate 中的 48 个 edition MP4）已逐文件
复算 SHA-256，与最终 aggregate CSV 完全一致。

没有闭合的 family 继续失败关闭：

- `ac4901` 的旧 v18 clean-story 候选仍是短小、近似重复且存在语音/可见说话动作
  不一致的无效提升；
- `ac7204` 是带角色语音的 gameplay/result family，尚未完成 story/result/effect
  的可靠拆分；
- `ac1101` 的 13 个注册 event 中 4 个仍缺生产 manifest，且存在替代 title/result
  分支碰撞、`ac1101_002` voice timing 和 mixed win/recovery composition 未闭合。

当前 `no_bgm_none/no_bgm_ja/no_bgm_zh` 是已获批继续扩产的独立轨道，含义始终是
“保留经证明的原始 voice/SE，明确排除 BGM”，不是“原游戏没有 BGM”。
`with_bgm` 仍等待具体 family 的继承曲目、入口 phase、volume、
fade/duck/replacement/stop 同 run 证据，不计入本轮成品。

提交前的内容正确性审查还关闭了四个发布风险：同目标并发 promotion 不再能删除
另一进程的有效输出；aggregate auditor 不再只信任自报的 SRT/AAC QA；series
proposal 必须绑定当前逐事件和上游 series hash；`環さん`／`黒江さん` 的项目所有者
称呼规则已进入构建与 QA。最新全仓回归为 354 passed、5 skipped、0
failed/error，真实 FFmpeg 集成测试已执行。

完整环境、路径、统计及语义边界见
`docs/research/2026-07-24-mass-no-bgm-production-and-environment-recovery.md`。

## 2026-07-18 非线性／多层剧情扩产等待人工播放

项目所有者已确认 Story 3/4/5 三部完整章节全部通过并授权全面生产，同时要求尽快
覆盖单全画面线性 SP Story 之外的内容。原话与三部 artifact hash 已保存为
`sp_story_3_5_full_chapters_owner_playback_20260718.json`。

首批跨 composition-class 候选已经生成：`ac1102`、`ac1103`、`ac1104`、`ac5208`
共 4 部、40 event、99 cue、175 audio layer 和 315.067 秒。其中 21 event 为
`linear_full_frame_sequence`，19 event 为 `timed_full_frame_layers`；覆盖多段全画面、
loop background、screen/loop overlay、416x232 与 512x288。四部均保持原生尺寸、
30/1 fps、H.264 与 AAC 48 kHz stereo，明确排除 BGM，自动 QA 全部通过。

耐久输出根：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\bilibili_mixed_composition_reviews_v22_20260718
```

本轮同时修复了 `_LP` 浮点时长多一帧和 timed framesync 少一帧的 CFR 边界，均改为
manifest 目标帧数驱动并保留逐帧失败关闭。全仓回归为 319 passed、4 skipped、
0 failed/error。四部仍为 `HUMAN_PLAYBACK_APPROVED=false`、
`BILIBILI_RELEASE_READY=false`；当前停止其余批量生产，等待项目所有者重点检查
runtime sparkle/logo 的 clean-story 归属、并发对白字幕、416x232 布局及 voice/SE。
完整 hash、统计和下一扩产边界见
`docs/research/2026-07-18-mixed-composition-expansion-review-batch.md`。

## 2026-07-18 首轮完整章节扩产已人工通过

项目所有者已确认首个 44.867 秒 `ac7114_001 -> ac7115_001 -> ac7116_001`
候选状态良好并授权生产更多视频。该授权按原话和首个候选 artifact hash 保存于
`tools/frida_runtime_probe/owner_attestations/`；它不冒充逐 cue 翻译批准或投稿授权。

现已把同一 no-BGM、voice/SE、中文字幕合同扩大到三个完整 family：Story 3
`ac7114` 12 event/35 cue/174.333 秒，Story 4 `ac7115` 9 event/34 cue/154.700 秒，
Story 5 `ac7116` 13 event/38 cue/187.900 秒。合计 34 event、107 cue、144 audio
layer、15,508 帧和 516.933 秒。三部均保持 512x288、30/1 fps、H.264 与 AAC 48 kHz
stereo；835/836 BGM 和 1681 金带声音失败关闭，无自动黑场或老虎机前景。

耐久输出根为：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\bilibili_expansion_reviews_v21_sp_story_20260718
```

三部自动 QA 均通过，项目所有者现已完成播放并明确确认“三部完整章节都通过”；
`HUMAN_PLAYBACK_APPROVED=true` 已作为 hash-bound owner attestation 保存，但这仍不
冒充上传授权或 `with_bgm` 批准。该结果正式证明“单全画面线性 SP Story”类别可以
批量化，并触发了上方的非线性／多层首批扩产。完整路径、hash、QA 和生产判断见
`docs/research/2026-07-18-sp-story-chapter-expansion-review-batch.md`。

## 2026-07-18 首个独立 R1 中文长片候选

项目所有者最新优先级允许 `bilibili_no_bgm_zh_v1` 在自身证据完整时独立达到
`BUILD_READY`，不再等待 `with_bgm` 及另两种字幕一起闭合。完整两音频母版乘三字幕
六版仍是最终 `archive_complete` 目标；本变化只解除了它对首个 R1 人工播放候选的
原子阻塞。

ac7114_001 -> ac7115_001 -> ac7116_001 已按证据顺序生成一个无自动黑场的长片：
1346 帧、2,153,600 个 48 kHz presentation samples、44.867 秒、512x288、30/1 fps、
H.264 1,053,224 bit/s 与 AAC 193,249 bit/s stereo。15 个 hash-bound OGG 组成 12 个
voice 与 3 个 scene SE；`bgm_layers=[]`，金带 request 1681 排除。9 条中文对白进入
SRT，`ごめんね…` 因 `graphical-only` 排除。

自动 QA 的 21 项检查全部通过；三个用户已确认 v19 声音 oracle 的双声道 APSNR
分别为 166.504/166.523、167.862/167.903、167.019/167.215 dB。P1 同名 runtime
event 静默 `last-wins` 也已关闭：冲突内容 fail closed，完全等价内容保存全部路径与
SHA-256 provenance。

耐久候选位于：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\bilibili_candidates_v21_no_bgm_zh_20260718\ac7114_16_sp_story_no_bgm_zh_v1
```

当前 `BUILD_READY=true`、`AUTOMATED_QA_PASSED=true`，但中文翻译和布局仍等待项目
所有者播放确认，所以 `HUMAN_PLAYBACK_APPROVED=false`、
`BILIBILI_RELEASE_READY=false`、`publishable=false`。已经停止第二部长片、批量生产、
素材分类与 BGM 捕获，等待反馈。完整合同、hash 和审查边界见
`docs/research/2026-07-18-first-independent-no-bgm-zh-candidate.md`。

## 2026-07-16 存储权威修正

A: RAMDISK 已关闭，当前及后续运行不得向 A: 写 scratch、证据或成片。耐久研究和媒体
统一落到 `D:\magia\MyProducts\casino`，C: SSD 用于正确 git worktree 和小型临时文件。
旧 A: 字符串只保留为 provenance；仅允许通过显式 `--path-prefix-map`、文件存在性和
source hash 三重核验解析到 D:，禁止重新建立 A: 依赖。

## 2026-07-16 全部 addon 与 CDN 结论

静态分析闭合 7 个 SKU/entitlement：index0 Save、1 Wait Cut、2 Settings、3 Auto、
4 Forced Role、5 Value Pack（0..4 合集）、6 Sound Pack。0/1/3 只影响运维和跑量；
2 改变台设定概率覆盖但随机 `?` 仍可用，五个角色按钮本身不读 entitlement；4 会
改变 forced lottery route，必须标 forced provenance；6 是唯一直接静音 222-ID 声音
集合的内容门。购买/恢复链没有另行下载媒体包。

PID3188 当前只读快照 14/14 字段读取成功且均为0：
`D:\magia\MyProducts\casino\runtime_recovery_20260716\evidence\addon_state_pid3188_readonly_20260716_01`；
capture manifest SHA-256
`FDADCE46BB6252F61356D4662D6696C2857A569294993B071E1A39F3E5E86E15`。

CDN 三个客户端声明边界对象于 2026-07-16 仍为 HTTP200、大小不变。392 个 OBB
分片、安装态 hash、7,801-video inventory 与官网均无 HLS/quality/高清 variant；当前
结论仍是可重拉 Android 原始资源，但没有隐藏高清母版路线。完整偏移、影响表和资源
异常收口见 `docs/research/2026-07-16-paid-addon-gates-and-archive-impact.md`。

进一步的静态枚举证明：免费随机设定会把 UI 值 6 严格解析为有效设定 0..5；固定
设定影响普通 Story 概率表，但 `fnLot_OT_AT_SpStryKnd` 不读取台设定。五个角色按钮
是 5 个 profile，正常 UI 的 custom voice 固定为 0，不是 5×5；强制役 0..19 又与
目标 SP Story `(stage, selector)` 属于不同编号域。故改变购买状态不会直接提高
ac7114/15/16 自然命中率，也不能闭合其继承 BGM。完整地址、映射表、事件码和建议
manifest 字段见 `docs/research/2026-07-16-setting-character-force-variant-space.md`。

中文字幕缺字路线也已从“依赖本机字体”升级为可复现依赖：固定
notofonts/noto-cjk `Sans2.004` commit
`523d033d6cb47f4a80c58a35753646f5c3608a78`，字体 SHA-256
`D68BAFCB48A2707749396AA12BBBD833CB70401F3A9A689FD2902C7E0D295964`，许可证
OFL-1.1 并单独固定 hash。真实字体已覆盖 ac7114/15/16 候选中文 34/34 码点，支持
首次下载、严格离线复验和显式 repair；它明确是非游戏原生的可审计中文字体。
候选翻译与布局仍未人工批准，`release_eligible=false`。见
`reproducibility/fonts/README.md`。

目标 BGM 上游 observer 也已通过当前 PID3188 零输入预检。MuMu 将 GameProc 以
`split_config.arm64_v8a.apk` 内 STORED ELF 直接映射；新门禁分别验证外层 APK
83,710,748 bytes/SHA-256 `89ACC81D...624E24`、内部 ELF 79,683,640 bytes/SHA-256
`5A0AE3CE...17EBF` 与 AArch64 header，再由已知 accessor 推导 runtime ELF base 并
核对 5 个 export offset。13/13 primary hooks 安装，0 unavailable/attach/probe error，
8 秒保留 973 条 sound metadata、0 drop、0 输入。journal SHA-256
`562A8F16864D6D0377CDC32E3F603338C4133A3DA37F4B5CF96D2204631C0F11`；详见
`docs/research/2026-07-15-target-sp-story-bgm-state-upstream.md`。

首个实际回合 `_04` 因 signature 错把 call ID/跨对象切换当状态而在 1024 条处失败
关闭，未冒充完整证据。改为 hook+对象分区并排除 call identity 后，生产函数 1000 次
重复抑制测试通过；修复后的自然 non-target `_06` 在真实负载仅发出 40 条上游记录、
0 drop/error，完整 sound trace 141 条，window 最终 closed，credit 47→44 且回到 0/0。
journal SHA-256
`7D8FA6761DAD9AF55405EC845FB0CB53CB0DF62D59D7CEC4C2234E4A4C84826E`。该回合没有
目标 SP Story/`kind=0x2f`/835/836，只证明 observer 已通过实战负载门禁。

发布工具的独立故障注入审查也已完成：series 改为 sidecar-bound PCM 精确拼接和每
profile 单次 AAC；scene/subtitle/material 使用同卷 staging、READY 与保留旧批次的
promotion；SRT 逐 cue 回读和来源双 rehash 关闭 TOCTOU；audio master 使用跨进程
mutex/no-replace/inode-safe rollback；material 使用 hash-bound 人审视觉语义和证据
trim/gain/duck；所有 identifier-derived 输出目录在写入前拒绝 traversal/drive/ADS/
reserved-name 与 symlink 根外逃逸。完整缺陷、修复及 289/289 验证见
`docs/research/2026-07-16-release-pipeline-hardening.md`。

## 2026-07-15 当前重连、可听 BGM 边界与 LC701A 静态闭合

MuMu 再次重启后，当前前台探针检查点为 PID3207；PID3125 仅为 dated evidence。
零输入、`execute=false` journal 位于
`D:\magia\MyProducts\casino\runtime_recovery_20260715\evidence\audible_bgm_pid3207_current_probe_readonly_20260715_01\hunt_journal.jsonl`，SHA-256 为
`68ECC94DF1C3B08C5CD51EAC72636FECBDA0E2CCCF67A9A983C15D34F3585A6D`。版本匹配的
222-ID Sound Pack 表通过 13 个 key check，初始 CSL active rows 为空。该空快照只
证明重连和探针 provenance 正常，不能反推此前五局没有 BGM。

用户确认 BGM 是在 PID3125 的五局 bounded non-target 批次中听到的。同批 ID800
runtime volume=0，已排除为可听贡献者；静态反汇编已经证明 ID835/836 均由
`C_ObjNml::fnSndRequest_BGM_DIR()` 直接生成，因此二者的 BGM 业务语义已经闭合。
尚未闭合的是人的听感与其中单一 ID 的同步绑定：五局结束约 14 分 35 秒后才做的
零输入跟随快照不能承担该唯一识别。

上游静态追踪又闭合了 `SdGmData+0x13da/+0x13de -> MSTCOMCBK+0xa72/+0xa76 ->
C_ObjNml+0xca/+0x11a -> fnSndRequest_BGM_DIR`。在 `kind=0x2f` 时 Direction no
`1..24` 选 835、`>=25` 选 836，但该状态有多条 commit/restore/clear writer；目标
SP Story 对象本地 sound 方法直接返回。ac7114/15/16 的 DirInfo 190/191/192 与
Direction no 无关，禁止据此推 836。详见
`docs/research/2026-07-15-target-sp-story-bgm-state-upstream.md`。

加固的 PID3125 snapshot audit 位于：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260715\evidence\runtime_sound_pack_snapshot_join_pid3125_hardened_20260715_01
runtime_sound_pack_audit.json SHA-256
7BD36419637B711A5C4CA051C35C289274673F944E93E6264686B2832B04D295
runtime_sound_pack_rows.csv SHA-256
3F28CDB1131A08A5EF19E6773A50FCEA9C61AC336099F733C8424F4C5D597094
runtime_sound_pack_pre_gate_volume_rows.csv SHA-256
7C01DC8CC2E14C5ABAFD1E8A5716C235D3AEB503BEEDB4C3232879EC76FBE992
```

它汇总 32 条 active row；4 条 gate row（唯一 ID800/801/821）全部为零音量，
unentitled corroborating/conflict 为 4/0，无效 snapshot 为 0。它是 snapshot-only
审计，pre-gate row 为 0，不能替代门控前音量或曲目语义证据。

LC701A 静态路线也向上游推进：已闭合 `VM[f070:f076] -> PC 040a/040c/040f ->
F7/ED31 -> DirInfo3`，并确定 `CplayData::LoadData` 是覆盖该区间的 native 持久化
writer；尚未找到自然抽选期间最后修改 `f070..f075` 的具体固件/native writer。
下一步是短时、只读的 writer-change probe，而非继续视觉猜测。详见
`docs/research/2026-07-15-lc701a-f070-native-writer.md`。

### 2026-07-15 声音 transport 已跨线程精确闭合

静态链已经闭合为 `SoundMng::sndPlayReq -> wrapSndReq -> CSndMng::SndReq ->
CSLMng::SndReq`。`sndPlayReq` 固定返回 `-1`，不能当 token；`PlayStart` 由另一个
Calc 线程调用。新的 probe 在 `CSLMng::SndReq` 保存游戏自己写入 `slot+0x20` 的
exact 12-byte row pointer，并用 `(CSLMng*, slot, row pointer, enqueue generation)`
与后续 PlayStart 对齐；同 slot 被覆盖时旧 pending key 会被删除。

首次八 hook 自然运行证据：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260715\evidence\natural_hunter_pid3207_cross_thread_csl_execute_20260715_03\hunt_journal.jsonl
SHA-256 42081908D49850F992AD7E58F892555505B7A964A6756C0D9947775DCFDD2E52
```

该次 130 条 sound trace 完整、0 drop、0 Frida error；9 个 enqueue 中 8 个被 exact
PlayStart 消费，1 个被同 slot 后续请求覆盖而正确不晋升。它还证明 original
resource `301` 可 remap 为 effective `43200` 并最终播放 `SSound_Data` ID `9002`，
所以 request/resource/final ID/OGG chunk 必须分字段保存。完整地址与边界见
`docs/research/2026-07-15-bgm-dir-and-csl-cross-thread-identity.md`。

### 2026-07-15 v20 真实画面、两条音频母版与六版 scene 门禁

`build_audio_base_masters.py` 已能从证据绑定的 clean visual、voice/SE 和 BGM layers
独立生成 `with_bgm` / `no_bgm` AAC 48 kHz stereo 母版，H.264 画面 stream-copy。
它验证逐包/逐帧 PTS、有效 presentation samples/PCM、源文件二次 rehash、码率合同和
mix peak；未知 loop、fade、`game_parameter` 或可能削波时拒绝生产，不擅自加 limiter。
两路视频和 sidecar 完成后才最后发布 transaction READY marker。

`render_subtitle_editions.py` 现在必须验证 marker、两路视频/sidecar、event-contract
hash、音频 timeline 和反向引用，才能派生 2×3 六版；所有版还必须保留相同编码画面
packet 和完整 frame/packet PTS timeline。`build_scene_editions.py` 的现代模式也已闭合
六版场景长片：按每个 event sidecar 的 `presentation_sample_count` 对有效 PCM 做 atrim，
连续 concat 后每个 with/no-BGM profile 只编码一次 AAC，并把同一母版复用到
none/JA/ZH；禁止直接拼 event AAC。tiny real-media 测试已覆盖直接 AAC concat 拒绝、
BGM 排除、voice/SE 保持、duck/restore、篡改和部分发布拒绝。

真实 v20 清单位于：

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\production_manifests_v20_frame_grid_20260715
event_production_summary.json SHA-256 9025608499EE13760A817CF8DF630AC08EE92F539EF6C13E1E2042835C2A58B2
event_production_catalog.csv  SHA-256 6E6D7C01CD98B11704543266D7E523254CBDCE37BA9A2C21CA8FCE90AC06A927
```

926 个 event 中 521 READY、405 fail-closed；显式 `--path-prefix-map` 把断电丢失的旧
A: provenance 指向已核验 D: 副本，不改写源 manifest。ac7114/15/16 均 READY 且无
A: 路径。其真实 clean visual 位于
`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\validation_outputs_v20_clean_visual_ac7114_16_20260715`，
均通过 512x288/30 fps/H.264/video-only QA，精确帧数 289/666/391，48 kHz presentation
samples 为 462400/1065600/625600。它们是可信画面输入，不是最终投稿成片。目标自然
事件的 BGM ID/phase/volume/transitions、中文 cue 审阅和游戏布局/字体仍未闭合，故尚未
晋升真实六版。

ARM64 Gadget 后续再注入 summary SHA-256 为
`44F1AB99BCD728C34AAD4A4838D97D444CE9FE27EC9B6B959E53E5F978C67534`；零输入 preflight
journal SHA-256 为 `E7B4FF3BC2DBE30702A74D48BA2BA5E6A6459A0F9345F5F668388B3D7CCFA8E6`。
随后两批各 5 次 bounded natural hunt 共 10 次全部 non-target、0 overflow、未伪报
target，正常 credit 最后为 19。journal SHA-256：
`6DA701E60A8CD3D5BAB25925C3DFAACC854FA3D6E139E1DB032D5855E7F2ECDE`、
`26902C0927129A1E0A7C4BBAD12F857768EA23FE56D8217A14BF41A6DA78436F`。不要无上限消耗
剩余 credit；这十次未把 ac7114/15/16 目标与 835/836 精确绑定。

将 `MAGIRECO_SLOT_ASSET_ROOT` 指向 D: 耐久真实资源后，当前全量自动验证为
289/289 passed、0 skipped/failed/error，四个 installed-asset JM 字形、真实 Noto
34/34 cmap 与真实 FFmpeg 事务/逐样本向量全部实际执行。全仓 `compileall`、
`node --check` 和
`git diff --check` 通过。

提交前审查同时关闭两项 scene 审计缺陷：modern summary 已放入各自 scene directory，
后建 scene 不再覆盖先前 READY 绑定的 summary；每事件 JA/ZH SRT 必须与已审计
`edition_plan` 的 cue count/start/end/text 完全一致，合并 SRT 写后还要 round-trip
回读。presentation samples 也改为按 rational frame rate 计算，并与 source manifest、
实际 frame timeline 及两套 sidecar 互证，已新增多 scene、漏 cue、写后篡改和
24000/1001 回归测试。

## 2026-07-14 Sound Pack 门控前混音与 2×3 发布规格

用户已明确：未授权 MuMu 的门控后静音不能成为停止 BGM 成片生产的理由。最终必须
生成 `with_bgm`（BGM+原生语音/SE）和 `no_bgm`（无 BGM、保留同源语音/SE）两条
母版，每条各有无字幕/日文/中文字幕，共 6 个 edition。

新探针只读挂接版本匹配的 `SoundMng::changeVolume@0x425ee68`，验证 222 项表严格
递增唯一并在 entitlement 分支前按原生整数链重建音量。PID3125 自然 non-target
运行捕获 ID826：bank01 OGG 33.000042 秒、SHA-256
`48F0455580E119CB92A86D6850356CBA68DA27BE62E69C107888C1E579DF1BEB`；原生
class/indexed/master=50/100/100，门控前 final volume=50，active index6=0 后 CSL
volume=0。跨 5 个 journal 的 join 还捕获 ID800/801/821/826 共 7 个 proven-playing
zero-volume rows，0 个矛盾；660 次旧逐帧 observation 压缩为 5 个 compact state
groups，不能冒充 5 次真实 transition。

权威 compact audit：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260714\evidence\runtime_sound_pack_join_pid3125_20260714_03
runtime_sound_pack_audit.json SHA-256
637C90791CB9BF65DC0FE72D0EF4B23288D80869A166AEFEB1C6F0D34938B2DC
runtime_sound_pack_rows.csv SHA-256
882138D9FDEC806B189891F20CC6C25D03BF8510C608A4C1F23ED440D6C34E68
runtime_sound_pack_pre_gate_volume_rows.csv SHA-256
28D7048CA6F8CCB77C0E8786E704BA203D126336309C18F33FC0529A88B0FE64
```

这证明外部 BGM 复刻可使用游戏自身的曲目和音量调度，不需要伪造 entitlement；但
ac7114/15/16 仍必须自然命中，才能获得同 run 的具体 BGM ID、入口循环相位、ducking
transition 和退出行为。详见
`docs/research/2026-07-14-sound-pack-pre-gate-runtime-volume.md`。

2×3 已有合同、真实 audio base-master 合成器、真实 clean-visual 接入、现代 scene
六路连续音频合成器和失败关闭的字幕/时间轴门禁：逐 voice/SE 与 BGM source hash、
timing、volume、BGM phase/loop/transitions、证据 artifact hash、字体 cmap、共用
game-layout profile、原生 H.264 signature/bitrate 均为硬门禁。当前剩余的是目标事件
BGM 合同、中文字幕人工审阅和目标媒体六版端到端验证，因此不会渲染或晋升伪六版。
详见
`docs/research/2026-07-14-two-audio-master-six-edition-contract.md`。

后续五局自然 non-target 中，用户确认实际听到 BGM；同批 runtime 出现不在 Sound
Pack 表内、volume=50、loop=1 的 ID835/836。两者现已由 `BGM_DIR` 原生业务调用链
证明为 BGM；精确到单一回合/场景的 ID、phase 和 transitions 仍需同步绑定，详见
`docs/research/2026-07-14-audible-bgm-observation.md`。

同步只读审计也修正了旧集合：ac0906/ac0912 是有效纯素材视觉集合；ac7204 的源
manifests 有 27 个角色语音事件，当前集合为 14 个唯一 AV 代表、4 个唯一 OGG，必须
降为 gameplay/result animation review。旧 audible mix 缺原生 volume/ducking 和
完整逐 OGG hash，只能 review。ac1102/1103/ac1104
旧 review 文件和 hash 完整，但 35/37 仍被 AV trust gate 阻止，且 ac1103_006/
_012/_013 混有胜利粒子/WIN 效果，不能直接发布为 clean story。2026-07-15 的只读
迁移 rehash 实查 family 120 个 source/output 文件，0 missing、0 hash error；ac0906
schema-v2 material collection 另查 36 个引用文件，0 error，仍是六个黑幕小 Kyubey
组件和 16 条 audio-evidence row。文件完整与语义可发布是两道不同门禁；两组旧 audible
mix 都不能冒充当前生产母版。

## 2026-07-14 PID3125 重连、字体纠错与 Sound Pack 门禁

MuMu 重启后的当前前台 PID 是 `3125`，所有旧 PID 都仅为 dated evidence。x86
server 直连只看到 `Process.arch=x64`，不能解析 ARM64 gameplay 导出；失败关闭的
只读 smoke journal SHA-256 为
`76024DABC98C089D9EC18C13D71079DAEE90E1EC405EF2D5711C29694356F887`。
重新加载 ARM64 Gadget 后，summary SHA-256 为
`179E136AF6E2B5B1DC0C90691F1F625C3D48CDD46F68CAA57DE7BF2BCB653AC5`。

新的 Gadget 只读 smoke 捕获 65/65 CSL slot、无 truncation、零输入、两端无 active
row；journal SHA-256 为
`E7BA647DDFBC8B166478367B53669D7786EBE4247DB4A442AAD9C661D4A941C1`。
随后 3 局有界 hunt 均完成 5/5 单次动作、三轴 0/1/2、7 个 dispatch batch、无
overflow，用时 3.934/4.013/3.898 秒；ID19 均为 `19 0 2 0 0 1 0 22`，故正确判为
non-target。journal SHA-256 为
`5A1D45FEF85D9EE706907172FFE7229FEBD592B43DF1F8FE7B572804EB3E6E6C`。
ID304 跨三局存在，但仍未获得业务 BGM 身份。

官方商店说明另售 Sound Pack 会解锁主要通常时 BGM 与 bonus music，所以无声运行
不能直接证明事件原生无 BGM；必须把 entitlement、音量和 native gate 与 PLAY/STOP
链一起记录。字体路线也已纠错：缺失的 `utf8/sjis_font_package` 是禁用 debug 路径，
真实故事字形是 DGI archive 中 4,124 个 JM Unicode glyph。现有日文语料 1,053 个
非空格码点覆盖完整，但该语料专用集合只覆盖约 8.46% GB2312 CJK，中文字幕需要
逐码点门禁和明确披露的 fallback。

当前 PID3125 的 provenance-complete 只读 entitlement 快照现已把该混杂因素定量
闭合：七项 addon 的 saved/active 均为 0，索引 6 Sound Pack 门禁未开启；零输入、
零 native call、零 memory write 的 `capture_manifest.json` SHA-256 为
`5932A15AF90BAA831B9EE2C7C08A4ADE077C4823C4567A81DC2D4214F694C89F`。
`SoundMng::changeVolume/checkEnableSoundID` 在该索引为 0 时扫描 222 个唯一声音 ID；
通用 play/channel request 都经过这条门禁。222 项中 219 项连接到当前
`sound_id_records.csv`，而当前 BGM/SE/Voice=50、master=100、Android 媒体音量未
静音。详见 `docs/research/2026-07-14-sound-pack-entitlement-gate.md`。ac7114/15/16
事件内的 420xx 对白不在表内，但 outer BGM 是否在事件前启动仍须自然入口边界捕获。

JM DGI 结论也已工具化：`extract_jm_dgi_glyph_catalog.py` 默认只读审计，显式请求时
才输出 JSON/CSV/原生 ASTC 4x4；每个字形记录 chunk/payload hash，缺任一中文字幕
码点退出 3。它明确不虚构 typography metrics、不解码、不 upscale。详见
`docs/research/2026-07-14-jm-dgi-glyph-catalog.md`。

ac7116 的尾帧命题不是剩余未知：已提交的同一次官方强制事件在
`ac7116_AT_SP_story5_01.dgm` end frame 337 后持续观察到
`GetDecodeFrame=337`、`IsDrawTime=1` 和 drawCall，覆盖 11.267--13.05 秒 voice tail。
断电丢失的是 7 月 3 日 A 盘原始 JSONL 审计副本，不是 Git 中已固化的机制结论。
自然目标重捕用于恢复原始链和闭合 outer BGM。当前 v19 两版虽时长/帧数正确，却是
约 1.09--1.11 Mb/s 的 libx264 重编码，低于现有主故事源约 1.506 Mb/s；最终六版仍
必须复核 codec/profile/bitrate 与一致的音频来源/hash。

## 2026-07-13 PID3083 active transport 与三局自然检查点

面向外部读者的最新中文汇总、静态/动态机制边界、2×3 六版本规格、CDN 备选路线
和量化剩余工作统一见：

```text
docs/HUMAN_PROGRESS_REPORT_2026-07-13.md
```

PID 11160 已降为历史证据。最近一次有效捕获 PID 为 `3083`；MuMu 重启后必须重新
读取前台 PID，任何 dated PID 都不得跨重启复用。PID 3189/8528 曾复现相同的
GLThread/Houdini 非法 PC 后 SIGSEGV/SEGV_MAPERR、fault `0xdead1005`，但现有栈
不能把崩溃归因于某一个 hook。

恢复顺序仍是：force-stop，先无 Gadget 启动并进入 Simulation，按一次
`ゲームスタート` 到真实 slot 主画面，再注入 ARM64 Gadget。Houdini 把游戏 ARM64
映射登记为 `split_config.arm64_v8a.apk`，所以探针按游戏专有导出定位所属映射，
不硬匹配 `libGameProc.so`。PID3083 reinject 证据为
`runtime_recovery_20260713\evidence\gadget_reinject_pid3083_20260713_01`，summary
SHA-256 为
`DA752417710EF91EFDE6B28F7EACA79E65B5215A1AC97AF35100453AEAAE924F`。

CSL active transport 前/后有界快照已经实现，不再是“下一步待实现”。当前只读
smoke 为 `natural_hunter_pid3083_active_csl_readonly_smoke_20260713_03`：零 gameplay
输入，声明/捕获 `65/65`、`truncated=false`，两端均无 active row；journal
SHA-256 为
`DA92840BC7E140AF1EF8A25E6BA77F97133E36ECA06BE375DDB666BE31F1A6CB`。
每次 RPC 临时挂到下一次 `CSLMng::Calc`，在 Calc thread 快照后 detach；128 是
防御 cap，不是游戏声明上限。

`natural_hunter_pid3083_active_csl_execute_20260713_01` 是一次有效普通 non-target。
五个输入各一次、三轴和累计 progress 正确、7 个 dispatch batch、无 overflow。
ID19 raw 为 `19 0 8 0 0 10 1 38`，零基 `raw[1]=0, raw[2]=8`，不能误判目标。
attempt-post 的 4 个 playing transport row 为 ID820/ch1、ID304/ch2、ID2655/ch3、
ID308/ch11，全部 `bgm_semantics_proven=false`。静态映射证明 ID820 是伊吕波对白、
ID2655 是 Sana title call；ID304/resource834 和 ID308/resource839 没有业务标签，
不能仅凭时长、channel 或 loop flag 叫 BGM。

本轮新增
`natural_hunter_pid3083_active_csl_execute_20260713_02`：三次自然局分别用时
4.080/3.990/3.780 秒，所有 15 个单次动作均接受，九次 STOP 均有轴 0/1/2 与
`0x200000/0x600000/0xe00000` 对应证据；每局 7 个真实 dispatch batch、无 overflow，
三局均为 `raw[1]=0, raw[2]=8` 的普通 non-target。journal SHA-256 为
`16B2929BD3FF6B6137AD29CF245F7708AA76D762024B1E11E572C77B581BD828`。

尚未开始无界搜索。下一道声音门禁是把 CSL transport 与 ZG published play-info
或等价官方 identity 绑定，并在同一次合法 ac7114/15/16 自然命中中证明 outer BGM；
CSL active row 本身不是 BGM 语义。ac7116 的 final-frame 337 hold 已由同一次官方
强制事件达到 runtime-mechanism 级证明；自然目标重捕只为恢复断电丢失的原始同源
日志并闭合 outer BGM，不再重开该机制命题。随后要实现 `with_bgm`/`no_bgm` 两条
母版各自的日文/中文/无字幕三版（日中共用时间轴/安全区，但允许分别绑定经 hash、
cmap、来源和许可证审计的字体，中文完整覆盖优先），并重新执行每条
母版内部的 codec/profile/bitrate/audio-hash QA。全库基线
仍为 926 events：
technical-ready 521，已有 per-event QA 304，ready 但缺 QA 217，仍需 series
decision 254，material collection 缺 323，严格 AV 门禁阻断 897。这些是库存门禁
计数，不是完成百分比。

## 2026-07-13 自然 SP Story hunter 与抽奖表权威增量

最新机制、失败审计、静态五表概率和面向人类的剩余工作量统一记录在：

```text
docs/research/2026-07-13-natural-sp-story-hunter-and-lottery.md
```

本轮纠正 2026-07-12 的“STOP 非零 process 位就是接受”表述：process 位只证明
触摸到达输入层。逻辑停轮还必须看到正确轴的 `CReel::setStopAngle`，并由
`state+0x64` 的 `0x200000/0x600000/0xe00000` 累计进度交叉确认。首停/两停间
门禁来自 `body+0x538/+0x53c/+0x540`，不是按钮颜色。新的 hunter 每个动作只发
一次，按 PID/前台/队列/主机时间和 sequence 水位失败关闭。

`extract_sp_story_kind_lottery.py` 已从原生 relocation 解析全部五张表并输出
JSON/CSV；所有权重和均为 32768。ac7115 的 `ごめんね…` cue 也已改为
graphical-only，清除未被运行时调用的 request 8894 元数据，不改动正确音轨。

PID 3189 在约 6559 秒 app lifetime 后崩溃回 Lawnchair；它已失效。其后曾恢复的
PID 7619/11160 也只是历史中间状态，当前必须以上方 PID3083 小节为准；旧证据目录
`runtime_recovery_20260713\evidence\gadget_reinject_pid7619_20260713_01` 仅保留审计。
ac7114/15/16 尚未捕获到新的合法自然 target batch；CSL active transport 捕获已
实现，但 ZG/业务 BGM identity 尚未闭合，不能晋升正式投稿。

## 2026-07-12 配额约束下的权威增量

最新 MuMu 重连、输入状态纠正、干净 sound-chain 自然验证、仓库树合并原则，
以及 926-event 剩余工作量，统一记录在：

```text
docs/research/2026-07-12-runtime-reconnect-and-completion-gap.md
```

本节的 PID `2636` 是 2026-07-12 历史快照，不是当前进程；当前 PID 见文首最新
小节。不要把任何 dated PID 跨重启复用。
远端只保留 `codex/corrected-runtime-pipeline`；D 盘资源根中的旧本地
`main@50e4f5d` 只作资源来源。旧状态被新状态覆盖时，以本节和核心 handoff
为准； dated research 继续保留作审计链。

本轮还纠正了一个新误区：`state+0x64` 的
`0/0x200000/0x600000/0xe00000` 序列表现为停轮进度/结果掩码，不能作为
stop-ready 门禁。输入是否被接受仍只看同次
`CSlotBody::process` 的非零位（max-bet 1048576、lever 524288、stop
2/4/8）。

## 2026-07-11 机制优先检查点

- 游戏/解包根目录已从旧 Downloads 路径迁移到
  `D:\magia\MyProducts\casino\com.universal777.magireco-Ga9DaxEd9F9Lqn9OVKVSfw==`。
  该目录中的 Git checkout 是废弃的本地 `main@50e4f5d`，不能用于代码工作。
  权威代码 worktree 仍是
  `C:\Users\cryne\.codex\worktrees\7454\com.universal777.magireco-Ga9DaxEd9F9Lqn9OVKVSfw==`
  的 `codex/corrected-runtime-pipeline`；目录移动导致的 worktree pointer 已修复。
- A: 继续只作可丢弃 RAM-disk scratch。D: 的
  `D:\magia\MyProducts\casino\runtime_recovery_20260710` 与
  `runtime_recovery_20260711` 保存最新持久证据。
- 最新机制报告：
  `docs/research/2026-07-11-generic-runtime-timeline-and-lc701a-helpers.md`。
  旧的“继续寻找谁把 0xfff0 写成 8”已被进一步闭合：
  `_USER_FC_CALL` 的扩展 helper 路径经过 `ASM_0xED31`，ED31 的 `r8`
  低/高字节成为 DirInfo3 `raw[1]/raw[2]`。此前只按两位十六进制名安装
  opcode hook，漏掉了 ED31/CB33/EDC7/EDD7。
- SP Story 候选现在采用严格同批门禁：同一真实 `accessSubProcess` batch 内
  必须同时出现 ID19 `raw[1]=8` 与合法 ID24 stage/selector。ID24 合法矩阵是
  stage11→1/2、stage12→1/2/3/4/13/14、stage13→1/2；packet id 统一使用
  `raw[0]&0x7f`。
- 最新自然一局持久证据：
  `D:\magia\MyProducts\casino\runtime_recovery_20260711\evidence\light_logic_state_driven_full_spin_20260711_02`。
  当前解析为 11,149 次 packet 观测、13 次实际 dispatch、26 次 copied-buffer
  观测、11,110 次 staging/state snapshot；DirInfo3 899/1、DirInfo8 1843/1
  （观测/dispatch）；两批命令大小 1/12；0 个完整 SP Story batch；0 hook
  error、0 parse error。batch 表现已保留 line/time/thread/getCmdBuf call count/
  buffer pointer/length，避免线程交错造成假关联。
- 通用调度层已定位到
  `DirectionControllerBase::pre -> PlayTableData -> PlayMacroData -> Macro_* ->`
  scene/sound request。小写 `pre()` 才是共享逐帧入口；旧的大写 `Pre()` hook
  会令 frame sequence 恒为 0。SE/BGM/FADE/EVENT queue 布局和
  `PlayMacroData` ABI 已静态确认。
- 上述自然局在约 111.4 s 调度的 scene event code 映射到 `ac0902_276`。
  code 291→request96→STOP；code295→request100→voice channel 0x9 STOP。
  实际 CSL id1360 是 resource16048、request3094、官方八千代对白，运行时
  875,556 bytes 与 9.120375 s、48 kHz、mono 官方 OGG 解码长度完全一致。
  `CSLStream` 不是 BGM 分类。
- 该局 `bgm_pending_queue_mutation_count=0`，只证明场景窗口没有新排入 BGM；
  尚不能证明进入事件前没有已经播放的 outer gameplay BGM。通用 v2 hook 已实现
  `codeName2ReqId -> zgSndReqId/getRequest/setRequestList -> performRequest ->`
  `sndPlayReq -> CSLMng::PlayStart` 的全量有界元数据链，说明见
  `docs/research/2026-07-11-sound-logic-chain-probe.md`。v2 只承认运行时 request ID、
  `ReqOrder+0x28` 静态 join key、同线程且实际嵌套于 `performRequest` 的
  `sndPlayReq`；CSL 不附加 recent context，必须走 sound-id 静态表。
  `D:\magia\MyProducts\casino\runtime_recovery_20260712\evidence\sound_logic_chain_probe_smoke_20260712_01`
  为 7/7 hook installed、0 unavailable/attach error。
- 首个同源自然声音日志
  `D:\magia\MyProducts\casino\runtime_recovery_20260711\evidence\joint_natural_spin_direction_sound_20260711_01`
  是 `ac0910_001`。其中旧版 `same_thread_recent/global_recent_window` 把后续
  order/resource/CSL 错挂到 code295，相关因果关联已全部作废；底层行仍直接记录
  request344/channel0 `PLAY`/resource814 与 request774/channel2 `PLAY`/resource2701。
  静态表闭合 `request344 -> code814 -> resource814 -> final287` 和
  `request774 -> resource2701 -> final6758`，同局也见 final287/6758；但 CSL 行
  本身无 request 因果上下文。code814/channel0 是强 outer-BGM 候选，BGM 最终
  语义仍需 v2 同局证据和 active-player 前后状态确认。
- 下一轮输入不得看蓝色按钮猜时机，也不得再把 `CSlotBody+0x454` 或 `+0x455`
  当逐轮许可；两者均已被运行态反证。先确认游戏 activity 在前台，再进入旋转逻辑
  状态；lever/每次 stop 只有在同次运行的 `CSlotBody::process` 实际收到对应非零
  input bit 时才算接受。`slot_state_gate_smoke_20260712_02` 在 idle 见
  `+0x454=1/+0x455=0`；`joint_natural_spin_mechanism_v3_20260712_01` 到 state3
  仍是同值，但 lever 接受行是 `input_a=524288`；旧完整局的已接受 STOP 行则是
  `input_a=2`。每次只试一个位置并保留该 process 行。目标是一次同源
  JSONL 绑定已接受输入、ID19+ID24、SP Story lottery、Direction frame/macro、
  场景码、PLAY/STOP、CSL 与 BGM 状态；未闭合前继续禁止批量晋升投稿成片。

## 2026-06-26 v18 当前状态

当前生产分支是 `codex/corrected-runtime-pipeline`。下载目录中的旧 `main`
检出不是权威工作树。

`production_manifests_v18` 当前覆盖 926 个事件，其中 521 个 render-ready、
405 个 failed、683 个 composition-resolved、405 个 audience-excluded、1615 条字幕。
当前 failed 全部有 audience exclusion reason；非排除 failed 队列为 0。
所有新增正式输出继续遵守：原生分辨率/帧率、不 upscale、不生成旧 124GB 1080p 输出、
不使用旧 motion/static 分类、不按 `ac` 后缀数字推 CRI index、不混合字幕版/无字幕版、
老虎机/按钮/粒子素材与正常动画分离。

最新新增：

- 2026-07-04 第二次 A: 丢失后继续推进：新增人类可读进度报告
  `docs/HUMAN_PROGRESS_REPORT_2026-07-04.md`，明确当前距离最终 Bilibili
  长片目标的工程差距。新增
  `tools/frida_runtime_probe/summarize_lightweight_spin_probe.py`，用于把
  `lightweight_spin_audio_probe.js` JSONL 固化解析为 packet/RxCom/lottery/BGM/
  queue/event-code/slot-state JSON+CSV。最新可靠完整一局物理输入捕获位于
  `D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_id401_cmd_buffer_full_spin_adb_continuation_20260704`，
  解析输出 `summary_lightweight_spin_probe_v2.json` 显示：JSONL 6,232,052
  bytes；9,660 条 packet 观测（含 staging 重复采样）；35 种唯一 raw packet；
  `candidate_count=0`；768 条 DirInfo3 packet 观测；6 条 RxCom rows；10 条
  lottery rows；162 条 BGM helper rows；2 条最终 audio queue rows；0 hook
  error；0 parse error。普通自然一局的完整 command buffer 中仍是
  `DirInfo3 raw [19,0,8,0,0,1,1,29]`，即 `raw_packet[2]=8` 而不是目标
  `raw_packet[1]=8`。因此普通完整 spin 仍未进入已证明的
  `fnRxComDirInfo3 payload[6]=8 -> SdGmData+0x358=8` story-dispatch route。
  但同一 run 证明外层普通 slot BGM helper 和 OpenSL queue 机制活跃，最终
  queue sound id 包括 `9002` 和 `60`；不能把旧渲染缺 BGM 解释为“游戏一定无
  BGM”。下一步应继续解 LC701A 上游如何写出 `packet_id=19 && raw_packet[1]=8`，
  而不是继续逐个 `ac` 视觉分类。
- 2026-07-04 二次断电恢复：A: 再次丢失，且这次未重新恢复 2026-06-29 备份；
  继续只把 A: 当可删除 scratch。D: 和 C: 保持安全，最新 durable evidence 仍在
  `D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence`。MuMu 重启后
  ADB 设备变为 `emulator-5554`，游戏前台为
  `com.universal777.magireco/.SlotMainActivity`。恢复 Frida 需要先启动设备内
  `/data/local/tmp/frida-server -l 0.0.0.0:27042`，再
  `adb -s emulator-5554 forward tcp:27042 tcp:27042`，运行
  `tools/frida_runtime_probe/reinject_gadget.py --adb-serial emulator-5554`，最后
  `adb -s emulator-5554 forward tcp:27043 tcp:27043`。成功证据：
  `D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\gadget_reinject_after_app_restart_second_loss_20260704`
  显示 PID `4207`、`gadget_arch=arm64`、`gadget_sees_libGameProc=true`；
  `light_probe_smoke_after_app_restart_second_loss_20260704` 显示
  `lightweight_spin_audio_probe.js` 42 个 hook installed、0 个 error-like 行。
  断电前/后尝试的长 `force_selector_probe` control sequence
  (`body_bet x3 -> lever -> stops`) 会出现 `another action is still pending`，
  且随后可导致 27043 `frida.TransportError: connection closed`，甚至 app 进程退出。
  后续完整一局 runtime 捕获应优先使用轻量 observer + ADB 物理输入
  (`2160x3840`; BET 约 `620,2475-2520`; lever `300,2680`; stop
  `830/1080/1320,2700`)，或改造控制脚本为同步等待 action_complete 后再发下一步。
- 2026-07-04 继续补齐 ID401 packet producer 机制：新增
  `docs/research/2026-07-04-id401-command-buffer-source.md`。静态证据表明
  `CSlotBody::analysPacket()` 先调用 `ID401::getCmdBuf(dst, 0xc00)`，再以
  8 字节记录循环调用 `ID401::accessSubProcess(packet)`；更上游是
  `LC701A_SLOT` 的 staging/queue 结构：`+0xf298` staging buffer、
  `+0xf0fe` pending length、`+0x200ed` queue flag、`+0x200ee` queue buffer、
  `+0x20cee` queue tail/counter-like field。`LC701A_SLOT::USER_LABEL_WORK()`
  和 `SET_BANKBUFFER()` 会把 staging packet 入队，`USER_LABEL_WORK()` 由
  `_USER_FC_CALL()` 调用。`lightweight_spin_audio_probe.js` 已新增
  `ID401::getCmdBuf`、`LC701A_SLOT::mn_getCmdBuf`、`USER_LABEL_WORK`、
  `SET_BANKBUFFER` command-buffer state hooks，并标记
  `packet_id=19 && raw_packet[1]=8` 作为 `fnRxComDirInfo3 payload[6]=8`
  的上游 lottery-dispatch candidate。最新真实输入短捕获位于
  `D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_id401_cmd_buffer_real_input_20260704`，
  只复制到 `fnRxComMedalIN` 包 `[4,3,3,156,240,0,0,150]`，未命中目标
  DirInfo3；这只是 instrumentation proof，不是机制负证据。后续应从
  STOP/result 状态延长捕获 LC701A queue，而不是继续逐个 ac 手工猜测。
- 2026-07-04 断电/恢复后，当前 durable 即时工作根继续改为
  `D:\magia\MyProducts\casino`；A: 视为 2026-06-29 备份恢复源和可删除
  RAM-disk scratch，不再作为唯一证据保存位置。新增轻量真实输入探针：
  `tools/frida_runtime_probe/lightweight_spin_audio_probe.js`，用于替代会导致
  MuMu/Frida 崩溃的重型 `csl_audio_queue_probe.js + force_selector_probe.js`
  实时输入组合。稳定证据位于
  `D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_physical_bet_calibration_20260704`：
  游戏保持前台，成功观察 `CSlotBody::START/STOP`、`fnRxComDirInfo8`、
  `fnRxComPreMdl`、`fnLotDirPreMdl`、10 条 event-code request 和 5 条
  `CSLMng::PlayStart`/final queue metadata；最终音频 queue 包括
  `sound_id=9002/60/61`。本次 ordinary spin 的 `fnRxComDirInfo8`
  payload `[4]/[5]/[6]` 全为 0，未触发 `fnLot_OT_AT_StryKnd/Chara` 或
  `C_ObjStageAT_SP_Story`，因此不是 ac7114-16 目标场景证据，不能解除 BGM
  门禁。失败的重型证据位于
  `D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\physical_input_spin_observe_20260704`；
  crash log 顶层在 `libmagireco_gadget.so!libfrida-gadget-raw.so`，应解释为
  observer-induced instability，不是游戏机制负证据。详细报告：
  `docs/research/2026-07-04-lightweight-real-input-audio-probe.md`。
- 2026-07-03 断电恢复后，稳定工作进度根改为
  `D:\magia\MyProducts\casino`；A: 只作为 RAM-disk scratch/2026-06-29 备份恢复源。
  `body_force_main` post-clear force kinds `0..19` 已完成有效扫描：旧 kind 8 曾映射到
  `ac0922_001`，新校准中 kind 8 可进入普通 `ac0101`/`ac0102`/`ac9071`/`ac9920`
  等路线；无论哪种结果，都没有任何一个进入
  `ac7114_001` / `ac7115_001` / `ac7115_013` / `ac7116_001` 的
  `C_ObjStageAT_SP_Story` 路线。新的静态证据显示 SP Story 路由是
  `(stage kind, selector)` 二元组：
  `MSTCOMCBK()+0x2376 -> C_AnmBase+0x318` 加
  `SdGmData+0x788 -> MSTCOMCBK()+0x2378 -> C_AnmBase+0x31a ->
  C_ObjStageAT_SP_Story+0x34a`，
  而不是 `ac` 后缀、单一 selector 或简单 force kind。新增
  `tools/frida_runtime_probe/survey_aarch64_xrefs.py` 用于自包含 ELF64/AArch64
  xref 调查；`csl_audio_queue_probe.js` 已新增
  `anm_base_data_set_dir_enter/leave` 与 `gr_dir_prm_copy_enter/leave`，
  `summarize_runtime_audio_capture.py` 会导出 `runtime_anm_dir_data.csv` 和
  `runtime_gr_dir_prm_copy.csv`。稳定静态输出位于
  `D:\magia\MyProducts\casino\runtime_recovery_20260703\static_xref_sp_story_selector_20260703`。
  2 秒 smoke 位于
  `D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\selector_hook_smoke_v2_20260703`：
  新 hook 已安装并生成 2253 条 selector rows，当前 idle selector 为 0；这只证明
  hook 可用，不证明 ac7114-16 route。为避免后续输出刷屏/丢后段 selector，
  `runtime_probe_host.py` 新增 `--quiet`，`run_force_kind_scan.py` 已使用它，selector
  hook 上限提升到每 kind 20000。上游复制器校准位于
  `D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\gr_dir_copy_force_kind8_v1_20260703`：
  `fnKndCalUsr_SetGR_DirPrmCopy` 真实触发 6 对 enter/leave，但
  `SdGmData+0x788`、`MSTCOMCBK()+0x2378` 和 `C_AnmBase+0x31a` 均为 0。
  新增 route-table 解码输出位于
  `D:\magia\MyProducts\casino\runtime_recovery_20260703\sp_story_event_code_extract_routes_v2_20260703`：
  `ac7114_001` = stage `11` selector `1/2`；
  `ac7115_001` = stage `12` selector `1/2/3/4`；
  `ac7115_013` = stage `12` selector `13/14`；
  `ac7116_001` = stage `13` selector `1/2`。下一步应跑窄 runtime
  stage/selector probe，不能继续盲目扩大 force kind 扫描。
- 同日后续静态推进：新增
  `tools/frida_runtime_probe/scan_aarch64_memory_offsets.py`，可按 AArch64
  内存偏移和短距离寄存器常量索引扫描 load/store。稳定输出：
  `D:\magia\MyProducts\casino\runtime_recovery_20260703\static_mem_offsets_register_index_v2_20260703`、
  `D:\magia\MyProducts\casino\runtime_recovery_20260703\static_mem_offsets_rx_stage_source_20260703`、
  `D:\magia\MyProducts\casino\runtime_recovery_20260703\static_xref_rxcom_dirinfo_20260703`。
  新结论：`MSTCOMCBK()+0x2376` 只有 `C_AnmBase::fnDataSetDir_DIR()` 的读点，
  暂未发现 direct writer；`fnKndCalUsr_SetGR_DirPrmCopy()` 写
  `MSTCOM+0x2370` 的 64-bit 零扩展值，会清掉包含 `+0x2376` 的高字节，
  不能当作 stage writer。更强上游线索是
  `fnRxComDirInfo8 payload[5] -> SdGmData+0x16e -> +0xee -> +0x31a`，
  `payload[4] -> SdGmData+0x170 -> +0xec -> +0x318`。这还不是最终
  `C_AnmBase+0x318/0x31a` 闭环证明，但已是当前最有价值的 stage/selector
  入口线索。`csl_audio_queue_probe.js` 已新增
  `rxcom_dirinfo8_*`、`rxcom_pre_mdl_*`、`lot_dir_pre_mdl_*` hook，
  `summarize_runtime_audio_capture.py` 新增 `runtime_rxcom_dir_flow.csv`。
  live smoke 位于
  `D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\rxcom_hook_smoke_20260703`
  和
  `D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\rxcom_force_kind8_probe_20260703`：
  新 hook 安装成功；单 kind 8 诊断触发 `rxcom_dir_flow_count=10`，但
  `sp_story_state_count=0`，`fnRxComDirInfo8 payload[4]/[5]` 均为 0，所有
  RxCom/SdGm stage/selector 字段保持 0，仍是非目标普通 route。
  `run_force_kind_scan.py` 已把 RxCom 计数和 payload/source stage/selector
  唯一值加入 `candidate_summary.json`。
- 2026-07-03 SP Story/force-routing 机制报告已新增：
  `docs/research/2026-07-03-sp-story-event-code-and-force-routing.md`。
  新工具 `tools/frida_runtime_probe/extract_sp_story_event_codes.py` 从
  `libGameProc.so` 的 `C_ObjStageAT_SP_Story::fnSetEvCdBase` 静态表提取 72 条
  base event-code 候选，并解析到 `ac7114_001`、`ac7115_001`、`ac7115_013`、
  `ac7116_001` 四条已 resolved manifest。`csl_audio_queue_probe.js` 已补充
  `sp_story_*` runtime hooks，`summarize_runtime_audio_capture.py` 会导出
  `runtime_sp_story_state.csv`。两次自然输入捕获
  `natural_slot_csl_bgm_input_v1_20260703` / `natural_slot_sp_story_audio_v2_20260703`
  证明普通老虎机外层能触发 BGM helper 与最终 CSL queue，但这两次均未进入
  `C_ObjStageAT_SP_Story`，不能解除 ac7114-16 BGM 门禁。可见 force UI 当前会被
  アドオン購入 门拦截；已新增 `force_selector_host.py body-force-main/body-force-sub/
  body-force-param` 直接写内部 `CSlotBody` force 状态，并验证
  `body-force-main --index 0` 可写入、`--index -1` 可复位，不触发购买 UI。该路线
  随后已用 post-clear diagnostic 完成 `0..19` 有效扫描，未命中 ac7114-16；当前
  下一步已改为 `MSTCOMCBK()+0x2378` / `C_AnmBase+0x31a` selector probe。
- 2026-07-02 ac7116 renderer texture-state 探针已新增：
  `docs/research/2026-07-02-ac7116-renderer-texture-state-probe.md`。
  新工具包括 `runtime_symbol_survey.js`、`cri_video_texture_probe.js` 和
  `summarize_cri_video_texture_probe.py`。全模块符号 survey 找到比
  `GLtask_display1/2` 更贴近实际路径的内部 renderer 符号：
  `RendererImplGL::checkAndBindTextureStates`、`TextureStateGL::bind`、
  `CScreenObjectMng::draw/calcFrameControl` 以及
  `CriVideo::GFDirectionRenderer::*`。GL export/eglGetProcAddress/OES draw
  探针只看到 0.074-0.080 s 与 6.707-6.715 s 的 512x288 texture
  allocation/bind/delete；11.267-13.05 s 语音尾段没有普通 GL texture upload、
  bind/delete、draw/sync/swap 证据。重启 app 并 reinject Gadget 后的 combined run
  位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_video_texture_ac7116_v5_combined_after_restart_20260702`：
  同一 run 中捕获主故事 `1e31c4fa`/1955904/512x288/30fps/338 帧，以及
  `sprite_renderer_check_bind_texture_states` 在 9-11 s、11.267-13.05 s、
  14-20 s 继续触发，且三段窗口均为同一 renderer/texture-state tuple
  `0x72b10b97f910` + `0x72af3cccff78` + flag `1`。该证据把
  `ac7116_001` 的 hold 从“动画对象/CRI receiver 支持”提升为“renderer path
  仍持续活动且状态稳定”支持；但仍不是 framebuffer/clean-layer pixel hash，最终
  B站投稿仍需 clean-layer pixel/texture proof 或明确接受该机制证据，outer-flow BGM
  门禁也仍未解除。2026-07-03 继续在
  `texture_state_fields_ac7116_v2_after_restart_20260703` 中加入
  `TextureStateGL` 前 0x80 字节的 metadata-only 数值字段采样；同一 run 再次捕获主故事
  `1e31c4fa`/1955904/512x288/30fps/338 帧，并在 11.267-13.05 s 尾段捕获
  20 次 `sprite_renderer_check_bind_texture_states`。三个 texture-state 指针
  `0x72af42645f58`、`0x72af42645f78`、`0x72af42646148` 均在尾段持续出现，
  且关键字段如 `+0x4=3553`、`+0xc=3`、`+0x68=194423728` 等保持稳定；
  其中 `+0x4=3553` 与 `GL_TEXTURE_2D` 一致，但结构布局未完全命名，不能直接把单个
  offset 当成最终 pixel proof。随后 `cri_video_texture_probe.js` 继续加入
  `RendererImplGL::drawCall(Primitive*)` primitive metadata 采样，v8 可用 run 位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_video_texture_ac7116_v8_primitive_after_restart_taps_20260703`：
  同一 run 捕获主故事 `1e31c4fa`/1955904/512x288/30fps/338 帧和 280 次
  renderer drawCall；在 11.267-13.05 s 尾段仍有 19 次
  `checkAndBindTextureStates` 与 19 次 `drawCall`。尾段保持同一 renderer
  `0x72b10b9830a0` 下的单纹理四顶点 primitive
  `0x72af405bd370`/`0x72af405bd168`/`0x72af405bd148`，分别带 texture id
  `155`/`151`/`150` 的稳定签名。该证据进一步证明游戏 renderer path 在主 338 帧后
  的语音/字幕尾段仍持续提交稳定 primitive，支持当前 clean `hold_last_frame` 策略；
  但仍不是 clean-layer framebuffer/pixel hash，且同 run 的 `89802b19`
  512x416/5277 帧 receiver 仍必须标记为 slot/gameplay/material 状态，不能当作 clean
  story continuation。已用同一 v8 JSONL 额外生成
  `summary_fine_windows`，确认三组稳定 primitive 在 0.5-6.6 s 主段、6.6-7.2 s
  LP 切换、7.2-11.0 s 中段、11.267-13.05 s 尾段和 14-20 s 后段均持续出现；
  该细分 summary 用于后续 layer correlation，仍不能直接命名 clean story primitive。
- 2026-07-03 继续从 static symbol survey 转向更直接的 Z2D movie-layer 路线：
  新增 `tools/frida_runtime_probe/z2d_movie_layer_probe.js` 与
  `tools/frida_runtime_probe/summarize_z2d_movie_layer_probe.py`，报告补充在
  `docs/research/2026-07-02-ac7116-renderer-texture-state-probe.md`。符号调查确认
  `zg::CZ2DPlayer::ExecPlayMovie`、`CZ2DHardPlayer::DecodeMovie/DrawMovie`、
  `CZ2DPlayMovie::*`、`CZ2DElemMovie::*` 与
  `CriVideo::GFDirectionCriPlayer::*` 是比旧 frame-lock hooks 更接近实际 movie
  调度的路径。forced `ac7116_001` v1 捕获位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\z2d_movie_layer_ac7116_v1_20260703`，
  `summary_v2` 识别到一个 512x288、start/end frame 0/337、decode frame 固定
  337、`IsDrawTime(337)=1`、texture-like id `151` 的 Z2D movie 对象；它与 renderer
  primitive `0x72af405bd168` / texture id `151` 对应，并在 11.267-13.05 s
  语音/字幕尾段继续 `ExecPlayMovie`、`GetDecodeFrame`、`DecodeMovie` 和
  `drawCall`。这把 `ac7116_001` 尾帧 hold 从“renderer stable primitive”提升为
  “Z2D movie-layer 以 end frame 337 原生持帧”强证据。随后按 force-stop/start/
  reinject/title-flow taps 重跑 v2，路径为
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\z2d_movie_layer_ac7116_v2_same_run_closure_20260703`：
  同一 run 在 121 ms 捕获主故事 `1e31c4fa`/1955904/512x288/338 帧，并命名
  `ac7116_AT_SP_story5_01.dgm` 的 Z2D 对象 `0x72affb9c0ae8` /
  `0x72affb9c0a98`，start/end frame 0/337，尾段 `IsDrawTime(337)=1`、
  `GetDecodeFrame(337)=337`，texture-like id `153`，renderer primitive
  `0x72af4e66e168` / texture id `153` 持续 drawCall 到 25.8 s。`ac7116_001`
  视觉尾帧 hold 现在应视为 runtime-mechanism 级闭环证明；BGM/outer-flow 门禁仍未解除，
  ac7114/ac7115 仍需同路线扩展。不要再把旧高层 frame-lock hook 作为主路线。
  随后同一 Z2D route 已扩展到 `ac7114_001` 与 `ac7115_001`，报告记录在
  `docs/research/2026-07-02-ac7114-16-cri-receiver-tail-sampler.md`。`ac7114`
  同 run 命中主故事 `a5b2c906`/1903456/512x288/275 帧与
  `ac7114_AT_SP_story3_01.dgm`，Z2D 对象 `0x72affba47728` /
  `0x72affba476d8` 在尾段 `IsDrawTime(274)=1`、`GetDecodeFrame(274)=274`，
  primitive `0x72af4e66e168` / texture id `165` 持续 draw。`ac7115` 同 run
  命中主故事 `4ad69770`/3940544/512x288/636 帧与
  `ac7115_AT_SP_story4_01.dgm`，Z2D 对象 `0x72affb9d0c28` /
  `0x72affb9d0bd8` 在尾段 `IsDrawTime(635)=1`、`GetDecodeFrame(635)=635`，
  primitive `0x72af4e66e168` / texture id `197` 持续 draw。至此
  `ac7114_001 + ac7115_001 + ac7116_001` clean story 的 visual tail-hold gate
  在 runtime-mechanism 级别已解决；下一关键门禁是 BGM/outer-flow audio proof。
- 2026-07-03 `visual_tail_probe.js` 以已恢复 Gadget 状态重跑 frame-lock 路线，结果位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\visual_tail_lock_ac7116_v10_20260703`。
  事件与 runtime 两侧均 exit 0，`summary_animation` 显示 88 个样本从 18 ms 覆盖到
  21829 ms，selected source 全部为 `C_AnmMain+0x350`，selected object
  `0x72b06b9870c0`、frame object `0x72b06b987510` 全程不变，`last_frame_age_ms`
  17-51 ms，selected object `+0x350` 从 4289 单调增到 4944。负证据同样重要：
  已安装的 `DirGetFrame`/`NotifyMovieStart`/`NotifyStartAnim`/`GetFrameInfo`/
  `IsFrameReady`/`CScreenObjectMng` lock-draw 高层 hook 在该 run 中全部 0 calls；
  runtime receiver 也只重捕获 foreground/gold-frame `c8fd6fe7`、`72e6f81c`、
  `c9cc7d28`、`f32a4a6b`，没有主故事 `1e31c4fa`。因此 v10 不能作为 main-clean
  identity proof；后续不要重复同一高层 hook set，应转向已知会触发的 lower renderer/
  compositor path 或 clean-layer texture/framebuffer hash。
- 2026-07-02 ac7116 animation-state sampler 已新增：
  `docs/research/2026-07-02-ac7116-animation-state-sampler.md`。
  新版 `event_scene_probe.js` 在 forced event context 活跃时每约 250 ms 输出
  `animation_state_sample`。成功捕获位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\animation_state_sampler_ac7116_v10_after_recovery_20260702`。
  结果：`ac7116_001` 从 16 ms 到 16817 ms 共 68 个采样，11.267-13.027 s
  声音/字幕尾段期间仍为 `C_AnmMain+0x350`、selected object
  `0x72b06b9bacc0`、frame object `0x72b06b9bcf40`，`last_frame_age_ms`
  保持几十毫秒。这证明官方动画系统在主 USM 338 帧结束后仍持续渲染同一故事动画对象；
  结合 v6 的主 USM 时长证据，`ac7116_001` 的 clean `hold_last_frame`
  现在可视为 runtime-supported mechanism-validation 行为，而不是纯外部拼接猜测。
  v11/v13 数值采样进一步发现 selected object `+0x350` 按约 30fps 单调递增，
  11.267-13.027 s 尾段不停止；该字段应视为动画对象时钟，不是 CRI movie frame
  index。v12 的宽泛 pointer scan 会导致 Frida/Gadget capture timeout，已将
  `includePointerProbe=false` 作为默认。仍未捕获 clean/story layer 的逐帧
  像素/texture 或 CRI frame index，所以最终 B站投稿仍受 clean-layer compositor
  proof 与 outer-flow BGM proof 门禁限制。新增通用解析脚本
  `tools/frida_runtime_probe/summarize_animation_state_samples.py`，用于把任意
  `event_scene_probe.js` 的 `animation_state_sample` JSONL 自动汇总为
  `animation_state_summary.json` 和 `animation_state_samples.csv`，避免后续继续手工
  逐个 ac 解析。随后 `visual_tail_probe.js` 新增 CRI receiver metadata sampler，
  并新增 `tools/frida_runtime_probe/summarize_cri_receiver_samples.py`。v16 重启 app
  并 reinject 后命中主 receiver `1e31c4fa`：512x288、30fps、338 帧，
  `cri_update` 覆盖 4-11134 ms，`GetStatus=5` 覆盖 267-10973 ms，receiver 数值采样
  到 20746 ms。该证据支持“主 CRI 到源时长后由上层动画/合成保持最后输出”，但仍不是
  clean-layer texture/pixel hash。
  同一方法已扩展到 `ac7114_001`/`ac7115_001`，报告位于
  `docs/research/2026-07-02-ac7114-16-cri-receiver-tail-sampler.md`：`ac7114`
  主 receiver `a5b2c906` 为 512x288/30fps/275 帧，`ac7115` 主 receiver
  `4ad69770` 为 512x288/30fps/636 帧。`ac7115` 另见 512x416/5277 帧大
  receiver `89802b19`，明确标记为非 clean story continuation。
- 2026-07-02 slot idle audio smoke 已记录到
  `docs/research/2026-06-28-audio-output-mechanism.md`：在恢复后的真实 slot
  gameplay 画面上分别运行 20 s `runtime_probe.js` 和 `csl_audio_queue_probe.js`，
  输出位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_idle_runtime_probe_20260702`
  与
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_idle_csl_queue_probe_20260702`。
  两者均没有非 hook 的 BGM/sound request 或 OpenSL play/enqueue 事件。这只证明当前
  idle slot 状态没有正在观测窗口内持续 enqueue 的 BGM，不能解除真实 story 触发路径的
  outer-flow BGM 门禁。
- 2026-07-03 `csl_audio_queue_probe.js` 已升级为同源 CSL+BGM 合并探针：同一次
  Frida run 同时记录 `libGameProc.so` 高层 sound-code/BGM helper 与 `libAMAIN.so`
  最终 `CSLAndroidSimpleBufferQueue::Enqueue` 队列，且单个高层 hook attach 失败不会
  中断后续 hook 安装。`summarize_runtime_audio_capture.py` 已适配该合并 JSONL 的
  sound-code/event-code 字段。验证捕获位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_bgm_combined_ac7116_v3_20260703`
  和
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_current_csl_bgm_combined_v2_20260703`。
  forced `ac7116_001` 同源捕获结果：38 个 hook 安装成功，`SndIsAlreadyPlayingBGM`
  1 个 attach error，BGM helper 行为 0，高层 sound-code 行为 13，最终 OpenSL queue
  仍只有 `42080_SPストーリー5_みふゆとももこ_01` / sound id `8912`、`8040_シネスコ変化音_金帯`
  / sound id `9544`、`31186_282_mihu_く…ぐ…` / sound id `8008` 三段。当前 live
  slot 状态 20 s 被动探针无 sound request、无 BGM helper、无 OpenSL enqueue。这强化
  forced ac7116 “无额外 BGM”结论，但仍不能解除自然 outer gameplay transition 门禁。
  同一 combined CSL+BGM 探针随后补跑 `ac7114_001` 与 `ac7115_001` forced path：
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_bgm_ac7114_v1_20260703`
  显示 5 个 `SoundMng::sndPlayReq`、5 个最终 queue chunk、0 个 BGM helper，声音链为
  `42040_SPストーリー3_01_2G`、`8040_シネスコ変化音_金帯 ` 和 3 条角色语音；
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_bgm_ac7115_v1_20260703`
  显示 10 个 `SoundMng::sndPlayReq`、10 个最终 queue chunk、0 个 BGM helper，声音链为
  `42060_SPストーリー4_かえでドッペル_01`、`8040_シネスコ変化音_金帯 ` 和 8 条角色语音。
  这补齐三段 forced official event path 的“无额外 BGM helper”证据；自然 outer-flow
  BGM 门禁仍未解除。
- 2026-06-28 ac7116 visual-tail 运行时探针报告已更新：
  `docs/research/2026-06-28-ac7116-visual-tail-runtime-probe.md`。
  v3 捕获位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\visual_tail_probe_ac7116_v3_20260628`，
  证明官方 `SetData` 命中了 gold-frame 前景层及 6.66 s 左右的 LP 前景切换：
  `AT_SPstory_gold_frame_add.usm`、`AT_SPstory_gold_frame.usm`、
  `AT_SPstory_gold_frame_add_LP.usm`、`AT_SPstory_gold_frame_LP.usm`。
  v6 在重启 app 并 reinject arm64 Gadget 后，直接观察到主故事
  `ac7116_AT_SP_story5_01.usm`
  (`patch_index=1321`, size `1955904`, first-4KiB FNV `1e31c4fa`) 的
  `CriManaWrapper::SetData`，且 `GetMovieInfo` 为 512x288、30 fps、338 帧
  （约 11.267 s）。这证明当前主视频源和时长是游戏运行时官方调度，不应换成旧
  416x232 restaurant/table 候选。但 v6 没捕获到 downstream frame/compositor
  证据，仍不能最终证明 clean 主画面在 11.267 s 后的尾帧 hold 是游戏原生；
  v7 官方 full-machine screenrecord 只证明前景 slot/title 层继续显示，不能代替
  clean/story layer 证明。`C_ObjNml::fnSndRequest_BGM_*` 的 per-frame helper
  调用也不是可听 BGM 证明。v8/v9 给 `visual_tail_probe.js` 增加了
  `split_config.arm64_v8a.apk` 模块解析和 offset fallback，能安装
  `GLtask_display1/2` hook，但这些 hook 在 forced event 窗口仍未触发，说明实际
  clean/story compositor 热路径还没打到。`csl_audio_queue_ac7116_v1_20260628`
  证明 forced official event 的最终 OpenSL 队列只有 request `42080`、`8040`、
  `31186`，无额外 BGM queue chunk；其中 `31186`/sound id `8008` 是 mono，
  `decode_csl_audio_queue_dump.py` 已新增默认 per-chunk 声道推断，避免把 4.144 s
  语音误判为 2.072 s。剩余 BGM 门禁现在是 outer gameplay/full-flow 捕获问题。
- 2026-06-28 交接与尾帧门禁修正：已新增核心交接文档
  `docs/HANDOFF_NEXT_AI_MAGIRECO.md`。用户确认
  `validation_outputs_v19_clean_audio_gate_ac7114_16_001_20260628` 的语音和字幕正确，
  但指出 `ac7116_001` 约 11 s 后画面静止、声音/字幕延续到约 13 s，且对是否缺
  BGM 存疑。复核结论：v19 没有删除 `420xx_SPストーリー...` bed/base-scene audio；
  `ac7116_001` 的静止尾巴来自 `hold_last_frame` 策略，保留最后角色语音
  `31186_282_mihu_く…ぐ…` 到 13027 ms。源 DGM `ac7116_AT_SP_story5_01.mp4`
  未检测到同等冻结，渲染版检测到 `freeze_start: 11.2`。因此当前 ac7114-16
  长片只能作为用户验证/机制验证输出，不能标为最终投稿成品；需要运行时画面或
  compositor/frame hook 证明尾帧 hold 是否为游戏原生行为，并继续用运行时 BGM/CSL
  queue 证据证明是否存在额外 BGM。
- `audit_runtime_av_trust.py` 已新增 `visual_tail_hold_ms`、
  `video_extension_policy`、`video_duration_ms` CSV 字段和
  `visual_tail_hold_needs_runtime_confirmation` 风险标记：角色语音事件若使用
  `hold_last_frame`/`black_tail` 且视觉尾巴 >= 750 ms，不再视为最终交付可信。
  v19 ac7114-16 子集重审位于
  `A:\magireco_corrected_research_20260612\runtime_av_trust_audits_v19_clean_audio_gate_tail_hold_20260628`，
  3/3 均保持 `blocked_pending_runtime_av_verification`；`ac7115_001` 与
  `ac7116_001` 命中新的尾帧确认门禁。全量 v18 manifest-only 重审位于
  `A:\magireco_corrected_research_20260612\runtime_av_trust_audits_v18_tail_hold_gate_20260628`，
  新门禁共命中 29 个事件。使用该 CSV 重算后的 strategy 位于
  `A:\magireco_corrected_research_20260612\pipeline_strategy_audits_v18_tail_hold_gate_20260628`；
  217 个 ready-missing 事件中仍只有 4 个 delivery-actionable，213 个保持 AV-blocked。
- 2026-06-28 clean-story 音频门禁修正：`audit_runtime_av_trust.py` 现在默认可全量审计
  manifest-root，区分 bed/base-scene audio、role voice 与 slot/foreground effect audio，
  并新增 `slot_or_foreground_effect_audio_in_clean_story_candidate`。全量 v18 manifest-only
  审计位于
  `A:\magireco_corrected_research_20260612\runtime_av_trust_audits_v18_clean_audio_gate_20260628`，
  926 个事件中 897 个仍被 AV 信任门禁阻塞，134 个命中 clean-story 中混入
  slot/foreground effect audio 的风险。
  使用该全量 AV trust CSV 重算后的 strategy 位于
  `A:\magireco_corrected_research_20260612\pipeline_strategy_audits_v18_clean_audio_gate_20260628`；
  217 个 ready-missing 事件中只有 4 个仍是 delivery-actionable，213 个转入
  `av_blocked_ready_missing_queue.csv`。
- `ac7114_001`、`ac7115_001`、`ac7116_001` 的 clean composition plans 已明确排除
  request `1681` / `8040_シネスコ変化音_金帯`，因为它属于被排除的 gold-frame/foreground
  slot 演出音效，不属于正常动画上传版。修正后的 production manifests 位于
  `A:\magireco_corrected_research_20260612\production_manifests_v19_clean_audio_gate_20260628`；
  修正后的单事件双版本位于
  `A:\magireco_corrected_research_20260612\validation_outputs_v19_clean_audio_gate_ac7114_16_001_20260628`，
  标准 QA 3/3 通过、非静音、字幕/无字幕音频一致、512x288、30/1、48 kHz 双声道。
- 已新增 `tools/frida_runtime_probe/build_scene_editions.py`，用于显式事件序列的同场景长片；
  旧 `build_series_editions.py` 只支持单 `acXXXX` 前缀 family，不适合 `ac7114 + ac7115 + ac7116`
  这种跨前缀同场景。已生成可审计 review 长片：
  `D:\MagiReco_Reverse\magireco_verified_scenes_v19_clean_audio_gate_20260628\ac7114_16_sp_story_clean_audio_gate`，
  含字幕版/无字幕版、合并 SRT、`scene_manifest.json`、`audit\scene_index.csv`、源文件 hash 和累计时间轴；
  scene-level QA 通过，3 段、44.854 s、10 条字幕、512x288、30/1、48 kHz 双声道。
  该输出用于用户验证；角色口型/视觉语音一致性仍按 AV trust gate 保持为最终交付前门禁。
- `ac5208_001`、`ac5208_002` 和 `ac5208_003` 已转为 clean story composition plans，
  剥离黑幕 `ac8002_chance_btn*` 按钮层和对应按钮提示音/押して声；`ac5208_003`
  采用主攻击层 `ac5208_lev_madhom` 归零、`ac5208_lev_madhom_LP` 从 4167 ms
  接续，并按官方 `40006_特化ﾏﾐ_追撃_まどほむ攻撃` 音频结束点渲染到 6740 ms；
  同时补入官方 request `8367 / 28016_CV_見滝原まだまだだよ` 字幕；
- `ac5208` 三个追击 clean story 单事件双版本已通过 3/3 QA；同场景长片候选也已
  stream-copy 生成并通过脚本 QA/视觉抽查，保持 512x288、30/1、48 kHz 双声道和
  双版本音频一致；
- 输出目录：
  `A:\magireco_corrected_research_20260612\validation_outputs_v18_clean_story_ac5208_full_v2`；
  长片目录：
  `D:\MagiReco_Reverse\magireco_verified_series_v18_clean_story_ac5208_20260626`；
- `ac2201_001` 已审计为 `黒江狙え` slot/gameplay cut-in，含押し順/狙え文字层和
  ADD/MUL 特效层，现从 clean story 队列排除并保留为素材/玩法候选；
- 57 个非 ready 的 `ac3102` RB slot battle/gameplay UI 事件已批量从 clean story
  队列排除，样本 `ac3102_007` 确认角色层自带按钮/图标/玩法文字；
- 24 个非 ready 的 `ac3103` RB roulette/gameplay UI 事件已批量从 clean story
  队列排除，样本 `ac3103_001` 确认叠层包含調整屋文字/图标/角色剪影玩法 UI；
- `ac5102_003` 已按静态生产证据转为 clean attack animation composition plan，
  渲染字幕/无字幕双版本并通过 1/1 QA；视觉抽查确认是伊吕波 magiatack 角色动画
  和粉色冲击背景，不含按钮、押し順、狙え或老虎机 UI 文本层；
- 19 个同结构 `ac5102` native 416x232 短攻击动画已小批量恢复，均为角色
  intro/LP 加同编号 `uwa_ef_bg_lp` 攻击背景，字幕来自官方 voice label，
  渲染字幕/无字幕双版本并通过 19/19 QA；输出目录为
  `A:\magireco_corrected_research_20260612\validation_outputs_v18_clean_story_ac5102_safe_shape_batch`；
- 剩余 120 个 `ac5102` mixed-dimension button-prompt 事件已从 clean story 队列排除，
  它们全部含 512x288 `ac8002_chance_btn_*` PUSH/連撃/長押し/連打玩法按钮层；
  保留为 gameplay/material collection 候选，不纳入正常动画长片；
- 6 个 `ac5004` Connect Chance title/selection UI 事件已从 clean story 队列排除，
  它们是 `コネクトチャンス` 标题和颜色抽选 UI，不属于正常剧情/动画成片；
- 24 个 `ac3407/ac3409` card-flip 上乗せ/PUSH UI 事件已从 clean story 队列排除，
  它们是 `ac3403_mekure_3on_*` 卡牌翻转和 `押して！` gameplay prompt；
- 15 个 `ac4904` SU/window framed character presentation 事件已从 clean story
  队列排除；角色内容位于小窗/卡框 UI 中，保留为 material/gameplay 候选；
- 16 个 `ac5201` 决战神浜黑底角色台词/动作事件已恢复为 clean animation，
  渲染字幕/无字幕双版本并通过 16/16 QA；输出目录为
  `A:\magireco_corrected_research_20260612\validation_outputs_v18_clean_story_ac5201_ch_serif_batch`；
- 20 个 `ac9051` 連撃 button-prompt UI 事件已从 clean story 队列排除；
  它们是纯 `ac8002_chance_btn_rengeki` / LP 按钮提示、PUSH 显示音和押して声，
  应保留为 gameplay/material collection 候选；
- 42 个 `ac0912` small-Kyubey guide / CHANCE / 激アツ / WIN / 上乗せ presentation
  事件已从 clean story 队列排除；抽样渲染 4/4 通过仅作为分类证据，视觉审计确认其为
  slot/gameplay guide 素材，不纳入投稿用正常动画长片；
- `ac0912` material collection 已生成并通过 manifest QA，保留 24 个去重组件、
  416x232、30/1 原生素材视频；另有官方音频可听审阅版，音频只来自当前 manifest 的
  官方事件音频证据；
- `reproducibility/project-kit/` 已建立，用于索引非 Python 探针/配置/清单、
  大型输入 fingerprint-only 策略和公开 Release 的派生证据边界。
- 2026-06-28 已发布 text-only derived evidence release
  `analysis-evidence-v18.27-20260628`：
  `magireco-analysis-evidence-v18-20260628-100858.zip`，12,765,785 bytes，
  SHA-256 `2D440A240CEF5A2A7F08D0B4FDE6D356A10CAF80655CA5E8370657000AD06797`。
  Release URL：
  `https://github.com/HiiragiNemu/magireco-slot-asset-pipeline/releases/tag/analysis-evidence-v18.27-20260628`。
  本地 bundle audit：1,599 个 evidence files、0 个 disallowed/media/binary
  extension、0 个绝对本机路径 pattern match；内容只包含 CSV/JSON/MD/TXT/SRT 派生证据，
  不含 `.jsonl` 原始 Frida 捕获、WAV、截图、视频、APK/OBB/native 库或游戏 payload。
- 2026-06-27 纠偏：用户复核确认 `ac0921_001` 缺预期 BGM，`ac4901_025/026`
  存在角色未张嘴但有语音/字幕的问题，`ac7204` material/result 输出含角色语音、
  不能称为纯素材；因此 technical QA/contact-sheet 不能再作为交付充分条件。
- 已新增 `tools/frida_runtime_probe/invalidated_output_roots.json`、
  `audit_runtime_av_trust.py`，并让 coverage/strategy 脚本读取作废根和 AV 信任审计；
  作废根保留在磁盘上用于审计，但不再计入完成覆盖。
- 通用化 pipeline 策略报告已重算，当前结论是：217 个 ready 但缺单事件 QA 的事件中，
  213 个仍是 linear full-frame 视频组合候选；但后续只能作为机制验证/批处理输入，
  不能在缺少运行时完整 BGM/SE/voice、字幕和视觉语音一致性证据时晋升为投稿成片。
- 2026-06-27 继续修正：`runtime_probe.js` 已补入高层声请求 hook，包括
  `C_CtrlSndLib::fnReqSndEventCode`、`fnReqSndSoundCode`、
  `fnReqSndSeqenceSC`、`fnReqSndSoundCodeCallBack`、
  `SoundMng_play_bySoundCd` 和 `SndReqBySoundCd`。这用于验证 `ac0921_001`
  这类静态 event timeline 缺 BGM 的样本是否由游戏全局/序列声调度层播放音频。
- `resolve_official_event_capture.py` 现在会输出 `actual_play_sound_count`、
  `high_level_sound_request_count`、`unresolved_sound_event_count` 和
  `unresolved_sound_events.csv`。高层声请求无法映射到 request/OGG 时必须显式保留为
  unresolved evidence，不能被当作完整音频轨。
- 新增 `diagnose_runtime_capture_state.py`。当前 MuMu 诊断输出位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\capture_state_20260627`，
  结论为 `blocked_x86_frida_cannot_see_arm64_game_code`：x86 Frida 可 attach 进程壳，
  但看不到 arm64 `libGameProc`；27043 ARM64 Gadget 仍不可达；arm64 frida-server 在
  native bridge 下仍连接即关闭；旧 Java-layer Gadget injector 在 x86 attach 表面报
  `Java is not defined`。因此在 Gadget 恢复前不生成新的投稿样片或批量成片。
- 2026-06-27 realm 复测输出位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\capture_state_realm_20260627`：
  default/native realm 都只能看到 `x64` 壳，均无 Java bridge、均看不到 `libGameProc`；
  emulated realm 返回 `ProtocolError('process is not using emulation')`；包本身
  `primaryCpuAbi=arm64-v8a`、`ro.debuggable=0`。捕获工具已补 `--realm native|emulated`
  入口以便未来环境验证，但当前状态仍不能恢复官方运行时 AV 捕获。
- 2026-06-27 Gadget 恢复：旧会话中的可用路线已固化为
  `tools/frida_runtime_probe/reinject_gadget.py`，通过 x86 frida-server endpoint 运行
  `inject_gadget.js`，加载 app 私有目录中的 ARM64 Gadget。当前 smoke 输出
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\gadget_reinject_tool_smoke4_20260627`
  为 `ok=true`，`gadget_arch=arm64`，且通过 `_ZN8CScnSlot4CalcEv` 导出反推到游戏映射；
  后续诊断
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\capture_state_after_gadget_reinject_v3_20260627`
  结论为 `runtime_capture_ready_via_arm64_gadget`。这只恢复了官方运行时取证能力；
  `ac0921/ac4901/ac7204` 等被作废样本仍需重新捕获、解析和人工验证后才可重新渲染。
- 2026-06-27 官方 code 重新捕获报告已写入
  `docs/research/2026-06-27-runtime-av-recapture-report.md`，后续 BGM 缺口复核写入
  `docs/research/2026-06-27-runtime-bgm-gap-report.md`。关键结论：
  `ac0921_001` 必须用长窗口解析，官方运行时在约 74 ms 播放
  `2990_次回予告_レバー`，后续有 4 条 Iroha 语音/字幕，并在约 27.46 秒才加载
  `ac0921_jikai_yokoku_3on_01(.lp)`；旧 15 秒 resolver 窗口会漏掉后段画面。但用户
  复核确认该 runtime-repair 样片全程无 BGM、约 23 秒后无语音，因此它是失败诊断样片，
  不能作为投稿成片或旧 v18 batch 的恢复证据。
  `ac4901_025/026` 和 `ac7204_003/017` 均有官方角色语音，不得归入纯素材；
  其中 `ac4901` 视觉说话校验不通过时也不得归入 clean-story 投稿候选。
- `resolve_official_event_capture.py` 已把空字符串声回调改写到
  `ignored_sound_events.csv`，并把默认解析窗口改为 60 秒。真实未解析音频仍保留在
  `unresolved_sound_events.csv` 和 `unresolved_sound_event_count`，不能被忽略。
- `ac0921_001` 的第一条 runtime-repair 用户复核样片已降级为 failed diagnostic：
  production manifest 位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\production_manifests_runtime_repair_v1_ac0921\events\ac0921_001.json`，
  渲染输出位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\validation_outputs_runtime_repair_v1_ac0921\ac0921_001`。
  虽然技术 QA 曾显示 1/1 passed、32.766 秒、416x232、30/1、48 kHz stereo、
  字幕/无字幕音频哈希一致，但用户复核发现全程缺 BGM 且尾段无语音；因此 contact sheet
  / stream QA 不能作为交付充分条件。
- `event_scene_probe.js` 的 `--with-sound` 官方路径已修通并记录
  `forced_event_sound_request_sent`，但 `ac0921_001` 诊断证明手动 event sound 只会多打一条
  `2990_次回予告_レバー`，不会补 BGM；`capture_official_event.py` 因此保留
  `--with-event-sound` 为诊断开关，默认不额外请求 event sound。
- `runtime_probe.js` 已补 BGM/request 层 hook：`zgSndReqCode/FadeCode/VolumeCode/PauseCode`、
  `SoundMng_isAlreadyPlayingBGM`、`C_ObjNml::fnSndRequest_BGM_*`、
  `C_DirectionControllerBase::Macro_SND_BGM_PLAY` 等。`ac0921_001` BGM-hook 捕获位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\official_bgm_hook_smoke_20260627`；
  事件窗口只见 lever SE 和 4 条 voice request，没有 BGM request，说明单 event 强制触发
  不进入外层 BGM 状态机。后续必须捕获完整触发流程或游戏最终混音，不能继续只靠单 event
  拼接生成投稿成片。
- 已新增 `tools/frida_runtime_probe/audio_output_probe.js` 作为游戏最终音频输出路径的
  metadata-only 探针。有效数值 code smoke 位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\audio_output_probe_ac0921_numeric_smoke_20260627`：
  `OutputCtrl::output` 捕获 265 个样本，其中 210 个为 output-enabled、5 个
  `TransBuf` 头部非零；事件侧仍只有 lever SE 和 4 条 Iroha 语音，没有 BGM request。
  这证明游戏混音出口可 hook，但 `TransBuf` PCM 布局尚未验证，不能据此生成投稿音频。
- `event_scene_host.py`、`capture_official_event.py` 和 `event_scene_probe.js` 已加
  numeric code 防呆：`--code` 必须是 resolved GBoss uint64，例如
  `0x544549382d424c4d`，`ac0921_001` 这类名称只能放在 `--label`。这避免 RPC 报错但
  pending request 已进入游戏而污染证据。
- 用户继续复核确认 `ac0921_001__subtitles.mp4` 无 BGM/不可听；文件级 audit 证明
  MP4 虽有 48 kHz stereo AAC 音轨，但 23 秒后到 32.766 秒尾段为实质静音
  (`mean/max=-91.0 dB`)。`qa_event_batch.py` 已补
  `manifest_audio_tail_gap` 和 `tail_digital_silence_after_manifest_audio` 门禁；重跑
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\validation_outputs_runtime_repair_v1_ac0921`
  后 `ac0921_001` 从旧 technical passed 改为 failed，记录
  `manifest_last_audio_end_ms=22777`、`manifest_audio_tail_gap_ms=9989`、
  `tail_max_volume_db=-91.0`。
- 2026-06-28 声音机制进展已写入
  `docs/research/2026-06-28-audio-output-mechanism.md`。静态证据确认
  `SndSystem::updateOutputBuf()` 先四平面混音并调用 `OutputCtrl::output(system+0xf78, ...)`，
  `OutputCtrl::output()` 会先检查 `[this+0x10]` 输出设备指针；当前 runtime
  `sound_device_state_ac0921_numeric_v3_20260628` 在 35 秒窗口内 46/46 个输出样本均为
  `output_device=0x0`，其中 23 个样本仍为 `output_enabled=1`。因此现在的阻塞点是
  游戏最终音频设备/全局 BGM 触发链没有被完整复现，不是继续按视觉拼接单 ac 能解决。
  已新增 `audio_output_buffer_probe.js`、`decode_audio_output_buffer_dump.py` 和
  `sound_device_state_probe.js` 用于后续从进程启动/设备初始化阶段继续破解。
- 2026-06-28 后续突破：`docs/research/2026-06-28-csl-audio-queue-runtime-capture.md`
  记录了 `libAMAIN.so` 实际可听 one-shot 路线：
  `CSndMng::SndReq -> CSLMng::SndReq -> CSLMng::PlayStart ->
  CSLAndroidSimpleBufferQueue::Enqueue`。新增
  `csl_audio_queue_probe.js` 和 `decode_csl_audio_queue_dump.py`，可把 OpenSL queue
  chunks 解码为 concat 或 runtime timeline WAV。`ac0921_001` 复测得到 5 段真实入队音频：
  request `2990/30031/30032/30077/30078` 对应 sound id
  `6893/6930/6931/6976/6977`；`--with-sound` 只额外重复请求 `2990`，没有产生额外
  BGM buffer。诊断 WAV 位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_audio_queue_ac0921_post_slot_v2_20260628\ac0921_001_runtime_audio_timeline.wav`
  和
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_audio_queue_ac0921_with_sound_v3_20260628\ac0921_001_with_sound_runtime_audio_timeline.wav`。
  这证明单 event 强制路径有权威 SE/voice 时间轴，但仍没有证明完整 BGM；继续禁止把
  `ac0921_001` 晋升为投稿成片，下一步必须捕获外层 gameplay/BGM 状态机。
- 2026-06-28 真实 slot 输入机制捕获已写入
  `docs/research/2026-06-28-slot-gameplay-audio-state-machine.md`。在 MuMu slot 主界面
  发送最小 lever/stop-button 输入后，运行时 event code 解析到
  `ac0001_001/ac9902_001/ac9010_060/ac9071_001/ac9100_001/ac9903_001/ac9920_001/ac9071_002/ac0910_001/ac0910_002`；
  `runtime_probe` 同时记录到反复的 `C_ObjNml::fnSndRequest_BGM_*`、
  1 次 `C_DirectionControllerBase::Macro_SND_BGM_PLAY`，以及 sound code
  `301/302/303/304/305/814/295/271` 通过
  `zgSndReqCode -> RequestCtrl::codeName2ReqId -> SoundMng` 进入请求层。
  `csl_audio_queue` 最终 OpenSL 队列捕获 15 个 dumped PCM chunks、48 kHz stereo、
  约 15.48 秒，observed sound ids 为 `60/61/62/6758/6759/9002`；另有
  sound id `287` / code `814` 的 3,072,004-byte chunk 因 per-chunk dump cap 只记录
  metadata，需要小范围提高 cap 复抓。诊断听音 WAV：
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_gameplay_input_probe_20260628\slot_gameplay_runtime_audio_timeline.wav`。
  这确认游戏机制是 runtime event-code + sound-code/request 状态机，不是手工逐个
  `ac` family 视觉分类；后续 manifest 必须以运行时请求和最终 OpenSL/官方解码证据为准。
- `tools/frida_runtime_probe/summarize_runtime_audio_capture.py` 已新增，用于把
  `runtime_probe.jsonl` 与 `csl_audio_queue.jsonl` 规整成可审计 CSV/JSON 表，而不是靠
  contact sheet 或人工截图判断。首轮 slot 捕获和大块重采样均已生成 `summary_tables`；
  大块重采样位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_gameplay_input_probe_large_chunk_20260628`，
  在 8 MiB per-chunk cap 下捕获 25 个完整 OpenSL queue chunks、约 19.86 秒、
  无 metadata-only chunks，observed sound ids 为
  `60/61/64/291/864/1768/6698/6709/8573/8575/9002`。该 run 走到不同随机 gameplay
  分支（`ac0908/ac0909`），没有复现早先 `814/287` 分支；因此 `814/287` 仍需定向状态
  steering 才能作为最终音频证据。
- `tools/frida_runtime_probe/build_runtime_evidence_skeleton.py` 已新增，用于把上述
  summary tables 与 `event_timeline_events.csv`、`event_timeline_sounds.csv`、
  `sound_request_struct_requests.csv` 和 `sound_id_records.csv` 离线合并为
  `runtime_evidence_skeleton.json`、`event_sequence.csv`、`sound_code_sequence.csv`、
  `play_request_sequence.csv`、`queue_sequence.csv` 和 `static_event_sounds.csv`。
  输出明确标记 `evidence_only_not_render_ready`：首轮 slot skeleton 保留
  metadata-only 警告；大块重采样 skeleton 无警告。它是后续批量 manifest 生成前的
  证据层，不会自动把诊断捕获晋升为投稿成片。
- 2026-06-28 定向 slot 输入复抓位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_targeted_814_probe_20260628`：
  8 轮 lever/stop 输入捕获 47 个完整 OpenSL queue chunks、约 41.40 秒、无
  metadata-only chunks，observed sound ids 包含 `287`。运行时确认 `814` 在
  `ac0910_001` 活跃窗口触发，`sound_code_sequence.csv` 映射为 request table id
  `344` / `213B22458D11890FF6BEEC183F22.smz`；`queue_sequence.csv` 中
  `sound_id_u16_at_0x2=287` 的 3,072,004-byte chunk 映射到
  `snd_00814_bank01_ogg_00287.ogg`。这解决了首轮 `814/287` 只记录 metadata 的缺口，
  但仍属于 gameplay/slot 机制证据，不是正常动画成片。
- `tools/frida_runtime_probe/package_runtime_evidence_capture.py` 已新增，用于把一次
  runtime capture 固化成可复现证据包：重新解码 OpenSL WAV、生成 summary tables、
  evidence skeleton、`source_hashes.csv`、`cumulative_runtime_timeline.csv`、
  `qa_report.json` 和 `package_manifest.json`。定向 `814/287` 捕获的证据包位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_targeted_814_probe_20260628\evidence_package_v1`，
  QA 状态为 `passed_evidence_not_delivery`，12 个关键文件已写 SHA-256，累计时间轴
  128 行。首轮 slot 捕获也用同一工具生成负例证据包：
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_gameplay_input_probe_20260628\evidence_package_v1`，
  QA 状态为 `failed_evidence_package`，失败原因是 `queue_metadata_count=1` 和
  skeleton metadata-only warning；这证明门禁会阻止不完整音频证据进入渲染。
- `tools/frida_runtime_probe/audit_runtime_evidence_packages.py` 已新增，用于扫描
  `evidence_package_v*` 并生成 package index。当前审计输出位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\runtime_evidence_package_audit_20260628`；
  结果为 2 个 package：`passed_evidence_not_delivery=1`、
  `failed_evidence_package=1`。失败检查统计为
  `no_metadata_only_queue_chunks=1`、`skeleton_has_no_warnings=1`。
- `tools/frida_runtime_probe/build_runtime_evidence_promotion_queue.py` 已新增，用于把
  package index 转成保守晋升/隔离队列。当前输出位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\runtime_evidence_promotion_queue_20260628`：
  首轮 failed package 被标记为 `blocked_failed_runtime_evidence_package`；定向
  `814/287` passed package 被标记为
  `runtime_gameplay_or_slot_material_with_dialogue_audio`，`clean_story_status` 为
  `not_eligible_gameplay_or_slot_sequence`。因此通过运行态音频 gate 仍不会自动进入
  normal animation / Bilibili clean-story 渲染。
- `report_pipeline_strategy.py` 已接入可选
  `--runtime-evidence-promotion-csv`，把 runtime evidence package gates 纳入全局
  pipeline strategy summary/report。重算输出位于
  `A:\magireco_corrected_research_20260612\pipeline_strategy_audits_v18_runtime_evidence_gate_20260628`；
  当前仍为 926 个 production events、521 ready、217 个 ready-missing，其中
  166 个不被 AV gate 阻断、51 个 AV-blocked。新增 runtime package gate 统计为
  `failed_evidence_package=1`、`passed_evidence_not_delivery=1`，promotion lanes 为
  `blocked_failed_runtime_evidence_package=1`、
  `runtime_gameplay_or_slot_material_with_dialogue_audio=1`，clean-story eligibility
  为 `not_eligible=1`、`not_eligible_gameplay_or_slot_sequence=1`。
- `tools/frida_smz_wav_probe.py` 已修正为全模块查找
  `zgSndCaptureConvertWav*`，因为当前 ARM64 Gadget 中导出位于
  `split_config.arm64_v8a.apk`，不是单独的 `libGameProc.so` 模块名。直接转换
  code `814` / raw media `213B22458D11890FF6BEEC183F22.smz` 目前返回 0 且不写 WAV；
  反汇编显示该导出依赖 zgsnd `SndSystem` 全局（`zgSndWinDllConstruction` /
  `zgSndInit` 路线），而当前可听路径是 `libAMAIN.so` `CSLSound` / OpenSL。因此
  官方 game-decoder 转 WAV 仍是后续破解路线，不能替代当前 OpenSL queue 取证。
- `audit_runtime_av_trust.py` 已从粗略 `voice_count` 改为 `role_voice_count`，
  不再把 BGM/SE/effect 的 `z2d_req_sound` 误判为角色语音；审计 CSV 新增
  `semantic_lane`。5 个官方重捕获样本的 lane 审计位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\runtime_lane_audit_bad_samples_v1`，
  结论是 5/5 仍为 `blocked_pending_runtime_av_verification`：
  `ac4901_025/026` 为短角色语音变体，`ac7204_003` 为 gameplay/result with
  role voice，`ac0921_001` 和 `ac7204_017` 为带角色语音、需视觉语音复核的动画候选。
- v18 trust/strategy 已用新版 lane/BGM gate 重算到
  `A:\magireco_corrected_research_20260612\runtime_av_trust_audits_v18_role_lane_v4_bgm_gap_20260627`
  和
  `A:\magireco_corrected_research_20260612\pipeline_strategy_audits_v18_role_lane_v4_bgm_gap_20260627`；
  ready-missing 217 中 166 仍为可行动渲染候选、51 个继续 AV-blocked。阻断 lane：
  31 个 `audible_gameplay_result_with_role_voice`、36 个
  `blocked_short_role_voice_variant`、11 个
  `normal_animation_candidate_needs_visual_speech_review`，另有 10 个
  `pure_gameplay_or_effect_material`。新增风险
  `long_role_voice_scene_without_bgm_or_bed_audio_evidence=2`，当前命中 `ac0921_001/002`。
- 新增 `audit_render_source_integrity.py`，用于给已渲染单事件补 source hash、
  event index、累计时间轴和输出哈希复核。`ac0921_001` 审计位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\validation_outputs_runtime_repair_v1_ac0921\ac0921_001\audit`：
  event_index=2814，event_key=`MLB-8IET`，3 个输入视频、5 个输入 OGG、
  4 条字幕，`output_hash_match=true`。
- `report_pipeline_strategy.py` 现在默认把 `invalidated_do_not_use` 和
  `blocked_pending_runtime_av_verification` 从 `ready_missing_queue.csv` /
  `verification_sample_queue.csv` 剥离，写入
  `av_blocked_ready_missing_queue.csv`。重算后 217 个 ready-missing 中只有 166 个仍在
  可行动渲染候选队列，51 个被 AV gate 拦截；验证抽样队列中 AV-blocked 事件数为 0。

当前已审计可观看集合仍以 v18 输出为准：

- `A:\magireco_corrected_research_20260612\validation_outputs_v18_clean_story_ac1102_04_full`
  与 `D:\MagiReco_Reverse\magireco_verified_series_v18_clean_story_ac1102_04_20260619`；
- `A:\magireco_corrected_research_20260612\validation_outputs_v18_clean_story_ac7206_full`
  与 `D:\MagiReco_Reverse\magireco_verified_series_v18_clean_story_ac7206_20260625`；
- `A:\magireco_corrected_research_20260612\validation_outputs_v18_clean_story_ac5208_full_v2`
  作为 ac5208 追击单事件 clean story 双版本；
- `D:\MagiReco_Reverse\magireco_verified_series_v18_clean_story_ac5208_20260626`
  作为 ac5208 追击同场景 Bilibili 长片候选；
- `A:\magireco_corrected_research_20260612\validation_outputs_v18_clean_story_ac4902_full`
  作为 ac4902 clean story 单事件双版本，46/46 QA 通过；
- `D:\MagiReco_Reverse\magireco_verified_series_v18_clean_story_ac4902_20260626`
  作为 ac4902 同场景 Bilibili 长片候选，46 段、约 11分30秒、59 条字幕。
- `D:\MagiReco_Reverse\magireco_material_collections_v18_audible_20260619\ac0906`
  作为素材合集，不混入 clean story。
- `D:\MagiReco_Reverse\magireco_material_collections_v18_audible_20260626\ac0912`
  作为 small-Kyubey / CHANCE / WIN / 上乗せ 等玩法素材合集，不混入 clean story。
- 2026-06-27 素材纯度 smoke 输出位于
  `A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\material_collection_purity_smoke_20260627`：
  `ac0912` 为 `pure_gameplay_or_effect_material`、`pure_material=true`、role voice=0；
  `ac7204` 为 `audible_gameplay_result_with_role_voice_not_pure_material`、
  `pure_material=false`；源 manifests 有 27 个角色语音事件，当前集合折成 14 个唯一
  AV 代表，因此不得作为纯素材或 clean-story 动画。
- 以下 v18 输出已作废为“不可交付，只保留审计”：generic strategy sample、
  `validation_outputs_v18_clean_story_ac4901_full`、
  `magireco_verified_series_v18_clean_story_ac4901_20260626`、
  `validation_outputs_v18_clean_story_ac7204_full`、
  `validation_outputs_v18_clean_story_ac7204_character_subset`、
  `magireco_verified_series_v18_clean_story_ac7204_character_subset_20260626`。
  这些输出曾通过技术 QA，但未证明运行时完整 BGM/SE/voice、字幕可靠性和视觉语音一致性。
- `ac7204` material collection 仍作为玩法/结果组件审计材料保留；但其 audible review
  edition 含角色语音，应归为“gameplay/result with role voice”，不是纯素材，不得混入
  clean story 或普通动画长片。旧 audible mix 还缺原生 volume/ducking 与逐 OGG
  source hash，所以不能标成 release eligible。

本轮复核结果：

- `ac1102`、`ac1103`、`ac1104` 的 v18 单事件 QA 列表、production manifest ready 列表、
  以及 `D:\MagiReco_Reverse\magireco_verified_series_v18_clean_story_ac1102_04_20260619`
  中三个 series manifest 的 sources 完全一致；没有漏 ready 事件或额外混入事件；
- `ac1102/ac1103/ac1104` 三个同场景长片均为 direct stream-copy，保留 416x232、
  30/1、48 kHz 双声道，series manifest 记录 cumulative timeline、每段 SHA-256、
  合并字幕和双版本音频哈希；
- `ac0906` material collection 复核为黑幕小 Kyubey 素材层，production manifest 中
  6 个事件全部带 audience exclusion reason；material manifest 分类为
  `reviewed_audience_components_not_standalone_animation`，没有混入 clean story。

全量覆盖缺口审计已生成：

```text
A:\magireco_corrected_research_20260612\coverage_audits_v18_20260626\event_coverage_v18.csv
A:\magireco_corrected_research_20260612\coverage_audits_v18_20260626\event_coverage_v18_summary.json
```

当前覆盖状态：

- 521 个 ready events 中，304 个已有未作废的 v18 单事件 QA，217 个仍需渲染/QA；
- 521 个 ready events 中，267 个已有未作废的同场景 series/preserved 覆盖，254 个仍需长片策略；
- 405 个 audience-excluded events 中，82 个已有 material collection 覆盖，323 个仍需素材归档或
  明确仅文档排除。
- AV 信任审计当前标记 78 个事件为 `invalidated_do_not_use`，10 个事件为
  `blocked_pending_runtime_av_verification`；详见
  `A:\magireco_corrected_research_20260612\pipeline_strategy_audits_v18_20260626\av_blocked_queue.csv`。

## 2026-06-18 运行时纠偏状态

本轮停止扩散旧的错误大批量输出，改为只沿“运行时证据 -> 生产清单 ->
单事件渲染 -> QA”链路推进。

当前新增确认：

- `ac1103_013` 已通过运行时捕获证明其官方链路包含独立角色语音、
  图形字幕和多层视频合成；
- `ac1102_006` 已按静态延长审计转为 `hold_last_frame`，现在保留
  官方音频尾声而不再因 482 ms 超时被拒绝；
- `ac1104_012` 已按静态延长审计转为 `hold_last_frame`，现在保留
  官方失败音频尾声而不再因 2586 ms 超时被拒绝；
- `ac1104_014` 已确认是 `c007/c007_LP` 底层全画面加
  `c009/c009_LP` 黑底 cut-in 叠层，现已纳入正式分层 plan；
- `production_manifests_v15` 已修复两个关键回归：
  `event_audio_components.csv` 的空 `ogg_path` 现在会按 `ogg_name`
  自动回填，`exact_gdb_frame_only` 图文字幕也重新纳入正式清单；
- 新的 `production_manifests_v15` 将该事件标记为
  `verified_native_composite`，原生尺寸固定为 `416x232`；
- 渲染结果严格分离为 `with_subtitles` / `without_subtitles` / `subtitles`
  三个目录，不再混放；
- 两个版本音轨哈希一致，且实际非静音；
- 不再创建 1920x1080 画布，也不再把非证实的 UI / 图标组件混入成片。

本轮有效输出：

```text
A:\magireco_corrected_research_20260612\validation_outputs_v15_ac1103_013
A:\magireco_corrected_research_20260612\validation_outputs_v15_ac1102_family
A:\magireco_corrected_research_20260612\validation_outputs_v15_ac1104_family
A:\magireco_corrected_research_20260612\validation_outputs_v15_ac0908_food_sample
```

便于人工复核的干净集合：

```text
A:\magireco_corrected_research_20260612\validated_ac1103_runtime_set_v1
A:\magireco_corrected_research_20260612\validated_ac1103_runtime_set_v2
```

其中 `validated_ac1103_runtime_set_v2` 为当前主集合，包含 4 条同一版
`v15` 清单下通过 QA 的事件样片：

- `ac1103_005`
- `ac1103_006`
- `ac1103_012`
- `ac1103_013`

`ac1103` 全 family 的 13 条事件也已经在同一版 `v15` 清单下完成渲染和 QA：

```text
A:\magireco_corrected_research_20260612\validation_outputs_v15_ac1103_all
A:\magireco_corrected_research_20260612\validated_ac1103_full_v15
```

详细证据见：

```text
docs/research/2026-06-18-ac1103-013-runtime-composite.md
docs/research/2026-06-18-ac1102-ac1104-family-fixes.md
```

## 2026-06-12 纠错状态

旧的“按尺寸判定完整画面后直接拼接”结论已作废。当前采用
`production_manifests_v2`：

- 146 个“全画面且语音已唯一匹配”候选中，119 个通过线性时间轴检查；
- 27 个存在重叠分支、合成层或无循环依据的长时间轴，已拒绝自动成片；
- 119 个事件均生成独立的有字幕版和无字幕版；
- 两版均保持源分辨率和帧率，不创建放大画布；
- 两版音频逐事件哈希一致，且全部实际非静音；
- 最终两套 MP4 合计约 516 MB，QA 失败 0。

当前结果：

```text
A:\magireco_corrected_research_20260612\production_outputs_v2
```

完整纠错证据见：

```text
docs/research/2026-06-12-corrective-runtime-audit.md
```

`DebugDispNameList.DIR_NAME_TBL` 中的 68 个北欧神话演出名属于共用引擎或
旧机型残留，不能用于魔法纪录成片命名。当前权威命名来源是 native
`EventInfo`、GDB/Z2D/DGM 映射和运行时 `fnReqScene`。

## 审计范围

已检查本地 APK/解包内容、JADX 输出、smali、native 字符串、GDB、`m_info.dat`、`sound_id.dat` 和现有提取脚本。

JADX CLI 输出目录：

```text
jadx_audit/base_src_only
```

JADX 输出文件数：1142。

## 关键代码层结论

Java/smali 层显示：

- `SlotMainActivity` 将 `cri.bin`, `cri2.bin`, `cri3.bin` 以及对应 add 表交给 `SysMng`
- `SysMng` 调用 native `nsysmSetCriFileNames` 和 `nsysmLoadOffset`
- 演出调试入口 `DebugProd.dispatchData(int,int,int,int,int)` 也是 native
- `DebugDispNameList` 和 `DebugProd` 提供演出标签，但不包含完整视频播放/拼合逻辑

native 层显示：

- `libARES.so` 包含 `CBinCtrl`, `LoadOffset`, `GetFileOffset`, `CRI_FUSION_FILENAME`, `MARGE_INFO_FILENAME`, `OGG_FUSION_FILENAME`, `SOUND_ID_FILENAME`
- `libGameProc.so` 含大量 `acXXXX`、图像/演出/音频资源字符串
- 实际资源选择、offset 读取、融合包处理和可能的演出调度主要在 native

## 资产统计

基础清单：

| 类型 | 数量 |
| --- | ---: |
| CRID 视频 chunk | 7801 |
| 唯一视频命名 | 483 |
| 多候选视频 chunk | 607 |
| 无直接视频候选 | 6711 |
| z2d chunk | 12083 |
| z2d 名称引用 | 11733 |
| OGG chunk | 9952 |
| `sound_id.dat` 记录 | 9951 |
| 含内嵌 `@SFA` 音频的视频 slice | 456 |
| PCM chunk | 21 |
| `m_info.dat` 记录 | 1084 |

内部审计：

| 项目 | 数量 |
| --- | ---: |
| Java/smali 关键文本引用 | 516 |
| native 方法声明 | 130 |
| native 相关字符串 | 41814 |
| native `ac` token | 34441 |
| native 序列候选 | 22979 |
| 视频序列候选 | 263 |
| 高置信视频序列候选 | 175 |
| 图像 `ac` 分组 | 256 |

## 视频命名与拼合判断

当前视频命名必须保守：

- 483 个 CRID chunk 可以唯一命名
- 多候选共享 chunk 不能强行命名为单一 `acXXXX_NNN`
- `ac0902`, `ac4921`, `ac0904`, `ac3409`, `ac3410`, `ac5102` 等存在长连续编号
- 这些长序列高置信，但很多 chunk 被多个演出名共享，所以只适合进入复核队列，不适合无条件自动拼合

当前建议：

- 先导出小样本视频，按 `video_sequence_candidates.csv` 人工或脚本核验画面连续性
- 对共享 chunk 建立画面 hash/时长/分辨率/音轨一致性检查后，再进入自动合并
- 未唯一命名的视频保留 `package + index`，避免误标

## 图像分类判断

z2d 的 GDB 名称引用足够多，可以按嵌入的 `acXXXX` 分组。

仍需注意：

- 大量 unclassified 图像可能是系统 UI、通用部件或非 `ac` 前缀资源
- 不应尝试伪装成 PNG；当前只导出 raw `.z2d`

## 音频判断

`sound_id.dat` 已解析为：

- 7 字节头
- 后续 9951 条记录
- 每条 12 字节
- 包含声音资源号、OGG chunk index、bank/category、固定 marker

OGG chunk 0 未映射，可能是保留项。chunk 1 起可以用：

```text
snd_<sound_resource_id>_bank<sound_bank>_ogg_<ogg_chunk_index>.ogg
```

示例：

```text
snd_00067_bank01_ogg_00001.ogg
```

视频内嵌音频判断：

- 全部 7801 个 CRID 视频 slice 中，456 个包含 `@SFA` 音频块
- `main`：230 个包含内嵌音频，4972 个不包含
- `patch`：226 个包含内嵌音频，2373 个不包含
- `ac0902_608..627` 样本没有 `@SFA`，所以导出 MP4 没有音轨是符合原始数据的
- `main:97` 样本包含 `@SFA`，导出后 `ffprobe` 显示 `h264 + alac`，说明内嵌音频解复用流程可工作

当前需要分清两类音频：

- CRID 内嵌 `@SFA`：可以随视频一起封装进 MP4
- 外部 OGG/PCM：需要从游戏事件、sound id 或 native 调度逻辑中建立对应关系，不能直接按视频文件名自动匹配

新增 `sound-request-audit` 后，已解析 `zg_snd_request_tbl.bin`：

| 项目 | 数量 |
| --- | ---: |
| 声音表可用字符串 | 22232 |
| 声音请求行 | 11249 |
| 可连接到 `sound_id.dat` 的请求行 | 9934 |
| 带描述标签的请求行 | 8501 |
| 附近存在 `.smz/.pcm` 媒体候选的请求行 | 11203 |

重要限制：

- 声音请求表内有大量语义标签，如 `seq_共通_発展`、`結果表示_WIN`、`セリフ` 等，可用于音频分类和人工复核。
- 当前未发现 `ac0902` 这类视频编号直接出现在声音请求表中。
- `nearest_media` 只是同表邻近候选，不能直接当作视频同步关系。
- 视频和外部 OGG/PCM 的最终同步关系仍需继续审计演出调度、事件表或 native 逻辑。

## 当前可用标准

项目已经达到“可继续批处理前的审计可用标准”：

- 能生成可复现清单
- 能区分唯一命名、多候选、无候选视频
- 能解析音频 ID 映射
- 能将图像按 `acXXXX` 做初步分类
- 会默认 dry-run，降低误操作风险

尚未达到“全自动最终整理标准”：

- 视频拼合仍需共享 chunk 复核
- z2d 真实图像格式仍需专门解码器或格式解析
- 音频和视频是否存在独立同步表尚未完全确认

## RAMDISK 全量导出复核

已使用 48GB RAMDISK 完成全量导出，并备份到：

```text
D:\MagiaRe_RAMDISK_Backup_20260603_032042
```

导出结果：

| 类型 | 数量 | 状态 |
| --- | ---: | --- |
| MP4 | 7801 | `ffprobe` 失败 0 |
| 含内嵌音轨 MP4 | 456 | 与 CRID `@SFA` 扫描一致 |
| 无内嵌音轨 MP4 | 7345 | 需要外部 OGG/PCM 关联审计 |
| OGG | 9952 | `ffprobe` 失败 0 |
| PCMRAW | 21 | 0 字节文件 0 |
| Z2D raw | 12083 | 0 字节文件 0 |

新增 `video-review` 命令后，已生成：

- `asset_manifests/video_review_sequences.csv`
- `asset_manifests/video_review_items.csv`
- `asset_manifests/video_review_unique_runs.csv`
- `asset_manifests/video_review_summary.md`
- `asset_manifests/video_review_concat_plans/`

复核结论：

- 263 个视频序列候选中，261 个仍涉及共享 chunk，不能直接最终合并
- 2 个序列存在同名映射歧义：`ac3409_263`, `ac8052_001`
- `ac0902` 后半段存在 26 个唯一连续片段，可用于视觉预览
- 已在 D 盘备份目录生成 26 个 `ac0902` 预览拼合 MP4，全部可被 `ffprobe` 读取，失败 0，均无音轨
- MP4 容器审计未发现“只有音频、没有视频流”的文件；7801 个 MP4 均有视频流
- 456 个含内嵌音频的 MP4 中，三帧采样发现 2 个全黑画面片段、2 个近黑画面片段，这可能解释“像只有声音没有画面”的观察
- `ac0902_*` 唯一命名视频共 483 个，全部无内嵌音轨；预览拼合后仍无音轨是符合原始 CRID 数据的

## RAMDISK B 站全量测试

已重新输出全量 MP4 到：

```text
A:\magireco_bili_fulltest_20260603\videos
```

本轮没有启用未验证的序列合并，也没有把外部 OGG/PCM 强行混入视频。输出策略是：

- CRID 内嵌 `@SFA` 音频：随视频封装进 MP4
- 无内嵌 `@SFA` 的视频：保持无声
- 外部 OGG/PCM：仅保留声音请求与标签候选，等待后续调度关系审计

结果：

| 项目 | 数量 |
| --- | ---: |
| 输出 MP4 | 7801 |
| 输出体积 | 3572329040 字节 |
| 有视频无音轨 | 7345 |
| 有视频有音轨 | 456 |
| 纯音频/无视频 MP4 | 0 |
| 全黑采样视频 | 133 |
| 近黑采样视频 | 259 |

特殊复核目录：

```text
A:\magireco_bili_fulltest_20260603\review_special
```

其中：

- `audio_only`：0 个文件
- `blackish_video`：133 个文件
- `mostly_black_video`：259 个文件

B 站元数据候选已生成：

```text
asset_manifests/bilibili_metadata_summary.md
asset_manifests/bilibili_video_metadata_candidates.csv
asset_manifests/bilibili_sound_label_candidates.csv
```

当前可获取的投稿辅助信息包括：

- 应用正式名：`スマスロ マギアレコード 魔法少女まどか☆マギカ外伝`
- APK 版本：`versionName 1.0.0`, `versionCode 31`
- 263 个视频序列候选的时长、分辨率、音轨数量、共享 chunk 状态
- 2480 条可读声音请求标签候选
- `ac` 图像分组和示例素材名，可辅助判断故事、角色、结尾、简介、UI 场景

## 2026-06-04 增量审计

### review_special 关系确认

`review_special` 目录是复核索引，不是原视频的唯一位置。当前在 NTFS 上优先使用 hardlink：

- `review_special\blackish_video\main_video_1150.mp4` 与 `videos\Unclassified_Slices\main_video_1150.mp4` 是同一文件数据的 hardlink
- `review_special\blackish_video\main_video_0529_candidates2.mp4` 与 `videos\MultiCandidate_Slices\main_video_0529_candidates2.mp4` 是同一文件数据的 hardlink

结论：

- 没有移动原视频
- `review_special` 中的文件仍在 `videos` 分类目录中可见
- `blackish_video` / `mostly_black_video` 只是亮度采样复核列表，不是删除列表；里面包含不少合法暗色素材、卡面、边框或 UI 片段

### 音频位置确认

当前 A 盘测试结果中：

- 带内嵌音频 MP4：`A:\magireco_bili_fulltest_20260603\review_audio\with_embedded_audio`
- 外部 OGG：`A:\magireco_bili_fulltest_20260603\audio_assets\audio\ogg_raw`
- 外部 PCM：`A:\magireco_bili_fulltest_20260603\audio_assets\audio\pcm_raw`

内嵌音频统计：

| 项目 | 数量 |
| --- | ---: |
| 有视频无音轨 MP4 | 7345 |
| 有视频有音轨 MP4 | 456 |
| `MultiCandidate_Slices` 中有音轨 | 49 |
| `Unclassified_Slices` 中有音轨 | 407 |
| `ac0902_演出` 中有音轨 | 0 |

456 个内嵌音频 MP4 的音频编码是 `alac`。外部 OGG/PCM 已导出并按 `sound_id.dat` 命名，但尚未找到可证明同步到具体视频片段的调度关系。

### 候选数连续段合并测试

新增命令：

```powershell
python magireco_asset_pipeline.py merge-candidate-runs --video-dir A:\magireco_bili_fulltest_20260603\videos --out-dir A:\magireco_bili_fulltest_20260603\merge_tests\candidate_runs_command_execute_hflip_video_only --execute --hflip --drop-audio --probe
```

规则：

- 只处理 `MultiCandidate_Slices`
- 文件名需匹配 `main_video_NNNN_candidatesX.mp4` 或 `patch_video_NNNN_candidatesX.mp4`
- 按 `package + index` 排序
- 仅当 index 连续且 `candidatesX` 相同时合并
- 单片仍输出一份，便于形成完整复核目录
- 本次执行使用 `--hflip --drop-audio`，因此输出为水平翻转校正后的 video-only 测试结果

结果：

| 项目 | 数量 |
| --- | ---: |
| 原 `MultiCandidate_Slices` MP4 | 607 |
| 输出 MP4 | 73 |
| 真正合并段 | 29 |
| 单片保留 | 44 |
| 执行失败 | 0 |

示例：

```text
main_video_0071-0099_candidates24.mp4
```

该文件来自 29 个源片段，时长 48.100 秒，源片段中 3 个带内嵌音频；当前测试输出故意去掉音频，避免混合“有音轨/无音轨”片段时产生错误合并。

### 镜像方向问题

用户复核确认当前导出视频存在左右镜像问题。本轮生成了方向样张：

```text
A:\magireco_bili_fulltest_20260603\orientation_check
```

候选数合并测试输出已使用 `hflip` 做水平翻转校正。原 `videos` 全量目录未被改写。

### 安装态拉取与完整性

通过 MuMu / adb root 拉取安装态内容到：

```text
A:\magireco_installed_pull_20260603
```

拉取结果：

| 目录 | 文件数 | 字节 |
| --- | ---: | ---: |
| `data_app_package` | 11 | 832841272 |
| `data_user_0` | 16 | 154288355 |
| `sdcard_Android_data` | 5 | 6158460910 |
| `sdcard_Android_obb` | 0 | 0 |

完整性判断：

- 安装态 6 个 APK/split APK 与项目目录本地 APK/split APK 的 SHA256 全部一致
- 安装态 `main.9...obb` 与 `patch.9...obb` 与本地 `downloaded_assets` 版本 SHA256 一致
- 因此现有 APK/JADX/apktool 输入和 Python 复刻下载得到的 OBB 主资源没有发现缺失或偏差

新增有价值内容：

```text
A:\magireco_installed_pull_20260603\data_user_0\files\assetpacks\OnDemandPack01\31\31\assets\smz.bin
A:\magireco_installed_pull_20260603\data_user_0\files\assetpacks\OnDemandPack01\31\31\assets\smz_add.bin
```

`smz_add.bin` 是 `smz.bin` 的 32-bit 小端偏移表，共 9753 个偏移，定义 9752 个资源块。2026-06-05 的增量审计修正了初步判断：它更可能是声音媒体容器，不是优先的图像/模型容器。

## 2026-06-05 声音媒体与 SMZ 增量审计

新增命令：

```powershell
python magireco_asset_pipeline.py sound-media-audit --smz-bin A:\magireco_installed_pull_20260603\data_user_0\files\assetpacks\OnDemandPack01\31\31\assets\smz.bin --smz-add A:\magireco_installed_pull_20260603\data_user_0\files\assetpacks\OnDemandPack01\31\31\assets\smz_add.bin
```

输出：

```text
asset_manifests/sound_hashreq_records.csv
asset_manifests/smz_chunk_header_audit.csv
asset_manifests/smz_name_chunk_map.csv
asset_manifests/smz_request_missing_from_installed_pack.csv
asset_manifests/pcm_name_table.csv
asset_manifests/sound_media_summary.md
```

关键结果：

| 项目 | 数量 |
| --- | ---: |
| 结构化 ReqData 唯一 SMZ 媒体名 | 9758 |
| 结构化 ReqData SMZ 引用 | 10944 |
| 结构化 ReqData 唯一 PCM 媒体名 | 21 |
| 结构化 ReqData PCM 引用 | 21 |
| `zg_snd_hashreq_tbl.bin` 记录 | 10420 |
| 通过记录序号关联到结构化 request 的 hash 行 | 10420 |
| 非零 `sample_count_u32` 行 | 9936 |
| 安装态 `smz.bin` chunk | 9752 |
| `loadFileSmz` relocated 名称 | 9752 |
| request 表中存在且安装态存在的 SMZ 名称 | 9752 |
| request 表有但安装态表无的 SMZ 名称 | 6 |
| 安装态有但 request 表未引用的 SMZ 名称 | 0 |
| `loadFilePcm` relocated 名称 | 21 |
| request 表中存在且安装态存在的 PCM 名称 | 21 |
| 推测 mono chunk | 6826 |
| 推测 stereo chunk | 2926 |

判断：

- `DecoderSmz::open_stream()` 使用 `loadFileSmz` 名称表查找媒体 basename，再使用 `g_SMZDataAddress[i]..[i+1]` 从 `smz.bin` 取 chunk；官方 SMZ 名称到 chunk 序号的映射已经可以生成。
- `SndInitManager()` 会把 `smz_add.bin` 读入 `g_SMZDataAddress`，把 `pcm_add.bin` 读入 `g_PCMDataAddress`。
- `zg_snd_hashreq_tbl.bin` 是 `64 + 10420 * 16` 字节；记录按 request index 对齐，结构为 `8-byte hash + sample_count_u32 + zero tail`。旧判断里的第三个字段不是 request id。
- 抽样切出的 `.smz` chunk 不能直接被 `ffprobe` 或简单跳过 header 的 MP3 探测识别；后续仍需要复用/还原游戏内 `DecoderSmz` 解码器，或做运行态音频捕获。
- 这次审计解决了“官方 SMZ 媒体名 -> 安装态 chunk”的地图，但仍没有证明外部声音与具体视频片段的同步关系。

对 B 站最终整理的影响：

- 已确认 456 个 MP4 本身带内嵌音轨，可优先作为有声候选。
- 7345 个无内嵌音轨 MP4 不能直接按 `.smz`、OGG 或 request id 强行配音。
- 可先用声音请求标签筛选投稿标题、说明和人工复核候选，例如 `魔法少女変身`、`マギア`、`ストーリー`、`WIN`、角色名等。

### Native 声音/视频字符串证据

新增命令：

```powershell
python magireco_asset_pipeline.py native-sound-video-audit
```

输出：

```text
asset_manifests/native_sound_video_evidence.csv
asset_manifests/native_sound_video_summary.md
```

结果：

| 类别 | 数量 |
| --- | ---: |
| `sound_media_table` | 6 |
| `sound_request_symbol` | 16 |
| `event_label` | 588 |
| `ac_play_method` | 15 |

关键证据：

- `smz.bin`, `smz_add.bin`, `zg_snd_hashreq_tbl.bin`, `sound_id.dat`, `ogg.bin`, `ogg_add.bin` 均出现在 native 字符串证据中。
- Java/smali 只暴露 `SndMng.nsmSndReq(int)` 入口，真正的声音请求路由仍在 native。
- `ac5406`, `ac5407`, `ac5408` 有专用 `fnSndRequest_BGM` native 符号，并且有 `EVT_ac` 标签。
- `ac1101` 至 `ac1206` 以及 `ac5209` 出现在 `C_ObjNml::fnSndRequest_BGM_DIR()` 证据中。
- `ac5102` 有 45 条 `EVT_ac` 标签，但当前字符串级审计没有看到直接 `sound_request_symbol`。
- `ac0902`, `ac4921`, `ac0904`, `ac3409`, `ac3410` 当前没有直接字符串级声音请求或 `EVT_ac` 证据。

判断：

- 该结果支持“视频/演出和声音存在 native 事件层关联”的方向。
- 但它仍是字符串级证据，不是最终同步表；不能据此自动把 OGG/SMZ 合并到 `ac0902` 或其他视频。

### ac5408 反汇编样本

本机没有现成 `objdump/readelf`，因此本轮使用纯 Python 解析 ELF `.dynsym`，并临时将 Capstone 安装到 `A:\TEMP\pydeps_capstone` 做只读反汇编。

关键函数地址：

| 函数 | 地址 | 大小 | 判断 |
| --- | ---: | ---: | --- |
| `C_ac5406::fnSndRequest_BGM()` | `0x43e9eb4` | 4 | 只有 `ret` |
| `C_ac5407::fnSndRequest_BGM()` | `0x43ea9e8` | 4 | 只有 `ret` |
| `C_ac5408::fnSndRequest_BGM()` | `0x43ec088` | 88 | 有实际逻辑 |

`ac5408` 相关函数中反汇编出的数字字符串：

| 来源函数 | 数字字符串 |
| --- | --- |
| `fnSndRequest_BGM` | `9078` |
| `fnPlaySND` | `296`, `283`, `6825`, `26497`, `6830`, `8032`, `1053`, `1052`, `1051`, `1050`, `1049` |

这些数字大多可以作为 `sound_resource_id` 映射到 OGG，但部分也能作为 `ogg_chunk_index` 映射到另一个声音资源。例如 `9078` 作为 request id 没有 OGG 映射，但作为 OGG chunk index 对应 `snd_04718_bank03_ogg_09078.ogg`。因此当前不能只按数字文本直接合并音频，必须继续确认调用函数语义。

PLT 解析后已确认关键调用语义：

| PLT 地址 | 符号 | 作用判断 |
| --- | --- | --- |
| `0x449ca00` | `_Z10CTRLSNDLIBv` | 获取声音控制库对象 |
| `0x449d5e0` | `C_CtrlSndLib::fnReqSndSoundCode(char const*, unsigned char)` | 按字符串声音代码请求声音 |
| `0x4492820` | `C_AnmBase::fnGetCallSignFlag(unsigned short)` | 演出标志判断 |

因此 `ac5408` 中的 `9078`, `296`, `283`, `6825`, `26497`, `6830`, `8032`, `1049-1053` 应优先解释为 `fnReqSndSoundCode` 的声音代码字符串，而不是 OGG chunk index。`9078` 虽然作为 OGG index 能落到 `snd_04718_bank03_ogg_09078.ogg`，但该解释目前低优先级。

进一步追踪已确认完整派发链：

```text
fnReqSndSoundCode -> fnSendSndData -> SndReceiveMessage(0x201)
  -> SndMngSetRequest -> SndMngFrameFunction -> zgSndReqCode -> zgSndReqId
```

这说明 `ac5408` 的数字字符串是官方声音代码输入。继续解析 `RequestCtrl::loadRequestTbl()` 后确认：code string 会映射到 `zg_snd_request_tbl.bin` 中的 request index，不等于 `sound_id.dat` 的 `sound_resource_id`。因此早期按 `sound_resource_id == code` 复制 OGG 的 `A:\magireco_bili_fulltest_20260603\sound_code_tests\ac5408_official_code_candidates` 已降级为低置信度参考。

新的结构化候选包位于：

```text
A:\magireco_bili_fulltest_20260603\sound_code_tests\ac5408_structured_code_to_smz
```

重点 code 的官方映射示例：

| code | request_id | first SMZ |
| --- | ---: | --- |
| `9078` | 2074 | `2A40747716A2B334129B4E859D42.smz` |
| `1049` | 444 | `F53FACA2830323AB642C1AD01802.smz` |
| `1050` | 445 | `83D6634F254D3A407E8028CC1732.smz` |
| `1051` | 446 | `22F05E94C422EDECF73A66E214B2.smz` |
| `1052` | 447 | `B91EA87EC141173B3EF70D8B4052.smz` |
| `1053` | 448 | `8A4A233E6BB8CFB14C79E1F234F2.smz` |
| `6825` | 1492 | `1622D09E2ADD3F9E609DCF959772.smz` |
| `6830` | 1497 | `37288F4F4F95C8C8146FA2035B22.smz` |
| `8032` | 1678 | `6C42AA7341BB599291C9B7D35312.smz` |
| `26497` | 8297 | `219AB8B97C4E29291BB44B4EFBB2.smz` |

### D 盘归档

本轮新增内容已复制到：

```text
D:\MagiaRe_RAMDISK_Delta_20260604_002343
```

归档内容包括：

- 候选数合并测试输出与 manifest
- 方向样张
- 带内嵌音频 MP4 复核集合
- `review_special` 复核目录
- `OnDemandPack01` 和小型运行态文件

没有重复归档全量 MP4、raw OGG/PCM、APK、OBB；这些已在旧 D 盘备份或本地工程中存在，且哈希/数量/总大小已验证一致。

## 2026-06-05 RAMDISK 修正状态

### 方向修正

用户人工确认原始全量目录仍是左右反向，包括：

```text
A:\magireco_bili_fulltest_20260603\videos
A:\magireco_bili_fulltest_20260603\review_special
A:\magireco_bili_fulltest_20260603\review_audio\with_embedded_audio
```

已新增 `hflip-videos` 命令，并在 A 盘生成方向正确的全量输出：

```text
A:\magireco_bili_fulltest_20260603\videos_hflip
```

执行结果：

| 项目 | 数量 |
| --- | ---: |
| 输入 MP4 | 7801 |
| NVENC 首轮成功 | 7031 |
| NVENC 因小尺寸失败 | 770 |
| libx264 补跑成功 | 770 |
| 最终 MP4 | 7801 |
| 0 字节输出 | 0 |

说明：

- 原始 `videos` 未移动、未覆盖。
- `videos_hflip` 是当前后续复核和投稿整理应使用的视频树。
- `hflip_manifest_nvenc_firstpass.csv` 保留了首轮 NVENC 失败证据；当前 `hflip_manifest.csv` 是 libx264 补跑结果。

### 内嵌音轨不等于可听声音

用户指出 `review_audio\with_embedded_audio` 中部分文件实际无声。已用 `ffmpeg volumedetect` 复核，确认旧分类只表示“MP4 容器有音频流”，不表示“有可听声音”。

关键样本：

| 文件 | 音频流 | mean_volume | max_volume | 判断 |
| --- | --- | ---: | ---: | --- |
| `Unclassified_Slices\main_video_2243.mp4` | `alac` | -91.0 dB | -91.0 dB | 静音音轨 |
| `Unclassified_Slices\patch_video_1343.mp4` | `alac` | -91.0 dB | -91.0 dB | 静音音轨 |
| `MultiCandidate_Slices\main_video_0097_candidates24.mp4` | `alac` | -10.3 dB | 0.0 dB | 可听音轨 |

已对方向正确的 `videos_hflip` 重新生成复核目录：

```text
A:\magireco_bili_fulltest_20260603\review_special_hflip_audible
```

结果：

| 类别 | 数量 |
| --- | ---: |
| normal | 7096 |
| silent_audio_track | 315 |
| mostly_black_video | 259 |
| blackish_video | 131 |
| audio_only | 0 |
| no_video_stream | 0 |
| probe_failed | 0 |

音频响度统计：

| audible_audio | 数量 |
| --- | ---: |
| yes | 141 |
| no | 315 |
| 空值/无音轨 | 7345 |

已单独硬链接出 141 个方向正确且真正有可听内嵌音频的视频：

```text
A:\magireco_bili_fulltest_20260603\review_audio_hflip\audible_embedded_audio
A:\magireco_bili_fulltest_20260603\review_audio_hflip\audible_embedded_audio_manifest.csv
```

### PCMRAW 转 WAV

`pcm_raw` 下的 21 个 `.pcmraw` 不能被 foobar2000 直接播放，因为它们不是 WAV 容器。探测结果显示每个文件是：

```text
32 字节自定义头 + s16le PCM payload
```

其中第一个 little-endian `u32` 等于 `文件长度 - 32`。

已新增 `convert-pcm-wav` 命令，并输出可播放 WAV：

```text
A:\magireco_bili_fulltest_20260603\audio_assets\audio\pcm_wav_48k_stereo
```

当前采用：

```text
s16le, 48000 Hz, stereo, skip 32 bytes
```

结果：

| 项目 | 数量 |
| --- | ---: |
| PCMRAW 输入 | 21 |
| WAV 输出成功 | 21 |
| 可听 WAV | 20 |
| 静音 WAV | 1 |

静音样本：

```text
pcm_00018.wav
```

### 安装态拉取价值

`A:\magireco_installed_pull_20260603` 已检查。相对旧 APK/下载包，最有价值的新增证据是安装态 Play Asset Delivery 目录：

```text
A:\magireco_installed_pull_20260603\data_user_0\files\assetpacks\OnDemandPack01\31\31\assets\smz.bin
A:\magireco_installed_pull_20260603\data_user_0\files\assetpacks\OnDemandPack01\31\31\assets\smz_add.bin
```

这些文件不在当前工程的 `unpacked_assets\assets` 常规资源目录中，必须保留用于 SMZ 声音研究。

当前哈希：

| 文件 | SHA256 |
| --- | --- |
| `smz.bin` | `AFBA721F0677DB90945711484D807C224250EDFA7E2945C4D1049B36777B501C` |
| `smz_add.bin` | `EAB5C3DE37CBCB8AD437106AC319EAB67D7DB5A65457177195D15B4D4ADA7F82` |

重新用安装态 `smz.bin/smz_add.bin` 执行 `sound-media-audit` 后确认：

| 项目 | 数量 |
| --- | ---: |
| runtime SMZ chunks | 9752 |
| runtime SMZ mono guess | 6826 |
| runtime SMZ stereo guess | 2926 |
| request 表有且安装态存在的 SMZ 名称 | 9752 |
| request 表有但安装态缺失的 SMZ 名称 | 6 |
| runtime SMZ 未被 request 表引用 | 0 |
| runtime PCM 名称 | 21 |
| request PCM 缺失 | 0 |

`sdcard_Android_data\files` 中的 OBB 与项目已有 OBB 尺寸一致；`gameData.bin/configData.bin/pad.bin` 目前只发现安装路径、访问状态和小型运行状态信息，没有发现新的演出命名或视频同步表。

### 本阶段 D 盘归档

已将本阶段 RAMDISK 研究成果固实压缩到：

```text
D:\MagiReco_Reverse\MagiaRe_RAMDISK_Research_20260605_hflip_audio_installed_pull.7z
```

归档范围：

```text
A:\magireco_bili_fulltest_20260603
A:\magireco_installed_pull_20260603
A:\timelines
```

未纳入归档：

- A 盘系统目录
- `A:\TEMP`
- Frida 临时下载/解压二进制
- 0 字节 `gamerecording.pb`

7-Zip 校验结果：

| 项目 | 数值 |
| --- | ---: |
| Folders | 86 |
| Files | 27904 |
| 原始大小 | 16163305230 bytes |
| 压缩大小 | 13731737346 bytes |
| `7z t` | Everything is Ok |

## 2026-06-05 运动审计与字幕候选

### 极短/静止视频审计

新增命令：

```powershell
python magireco_asset_pipeline.py motion-audit --video-dir A:\magireco_bili_fulltest_20260603\videos_hflip --out-dir A:\magireco_bili_fulltest_20260603\motion_audit_videos_hflip --collect-review --workers 4
```

全量方向正确视频树结果：

| 类别 | 数量 |
| --- | ---: |
| normal_motion | 2671 |
| very_short | 2371 |
| short | 1530 |
| low_motion | 490 |
| short_static | 426 |
| static_like | 313 |

真正可听内嵌音轨的 141 个视频结果：

| 类别 | 数量 |
| --- | ---: |
| normal_motion | 93 |
| short | 17 |
| low_motion | 16 |
| static_like | 8 |
| very_short | 4 |
| short_static | 3 |

关键判断：

- 大量 1 秒以内视频、短静止视频是游戏素材/分支/触发资源形态，不是导出脚本单点失败。
- `main_video_0294_candidates4.mp4` 和 `main_video_0303_candidates4.mp4` 有音轨但极短且低运动，人工听感接近无声是合理的。
- `patch_video_1199.mp4` 和 `patch_video_1205.mp4` 属于正常运动长片段；上下镜像更像场景内反射构图，不是需要修正的整体方向问题。

当前审查目录：

```text
A:\magireco_bili_fulltest_20260603\motion_audit_audible_embedded
A:\magireco_bili_fulltest_20260603\motion_audit_videos_hflip
```

### 字幕/台词候选

新增命令：

```powershell
python magireco_asset_pipeline.py subtitle-candidates
```

输出：

```text
asset_manifests\subtitle_dialogue_candidates.csv
asset_manifests\subtitle_dialogue_candidates_summary.md
```

严格台词候选：

| 项目 | 数量 |
| --- | ---: |
| 台词行 | 896 |
| 可连接 runtime SMZ | 896 |
| 可连接 OGG 命名 | 886 |
| 解析出 `subtitle_text` | 877 |

判断：

- 项目已经能提取大量官方台词标签，可作为字幕版文本初稿。
- 这些不是 timed subtitles；最终字幕还需要事件时间轴、SMZ/OGG 解码时长或人工对齐。
- 原始标签存在截断，不能把 `subtitle_text` 直接视为完整官方台本。

### SMZ 状态修正

`DecoderSmz` native 符号包含 `frame_get_side_info`、`frame_get_scale_factors`、`frame_dequantize_sample`、`dct36/dct64`、`decode_frame`、`openForConvert` 等 MP3 Layer III 风格流程。

当前判断：

- SMZ 不是简单“跳过 header 后交给 ffmpeg”的容器。
- chunk 前 32 字节为自定义头，后续没有标准 MPEG frame sync。
- 官方解码优先路线仍是调用游戏自身 `zgSndCaptureConvertWav*`；MuMu x86_64 + arm64 native bridge 环境下 Frida 仍不稳定。
- 静态路线需要还原 `DecoderSmz::openForConvert/read_frame/decode_frame`，成本高于简单解包。

### 本轮归档

已重新归档包含运动审计和字幕候选的 A 盘研究目录：

```text
D:\MagiReco_Reverse\MagiaRe_RAMDISK_Research_20260605_motion_subtitle.7z
```

校验结果：

| 项目 | 数值 |
| --- | ---: |
| Folders | 118 |
| Files | 31543 |
| 原始大小 | 16639306919 bytes |
| 压缩大小 | 14999419536 bytes |
| Solid | yes |
| `7z t` | Everything is Ok |

## 2026-07-03 断电恢复与当前工作根

断电后 A: RAM disk 上 2026-07-03 的临时运行捕获不可再视为可靠现存证据。用户已把 2026-06-29 备份恢复到 A:，并解压到新的持久工作目录：

```text
D:\magia\MyProducts\casino
```

当前策略：

- Git 仓库和 C: worktree 作为脚本、研究记录、交接文档的主状态。
- D: 用作断电后持久运行证据和即时工作进度：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence
```

- A: 只用于可丢弃高频 scratch；需要进入 QA、manifest、交接 MD 或最终 Bilibili 交付判断的证据必须复制/生成到 Git/C/D。

当前已恢复/确认的 2026-07-03 进度：

- 正确分支：`codex/corrected-runtime-pipeline`
- 已推送提交：`3d15644 Record SP story force routing evidence`
- 已推送断电恢复提交：`4ce6992 Record force recovery probes after power loss`
- 已推送 post-clear force 提交：`109f3b6 Record post-clear force mapping evidence`
- 该提交保存了 SP Story event-code 静态提取器、force routing 研究记录、ac7114/ac7115/ac7116 运行时结论和交接状态。
- `4ce6992` 已保存 `force_flag_*` observer、`body-reel-start` 诊断 action 和 `runtime_force_calls.csv` 汇总输出。它们用于继续证明外层调度/force 消费，而不是直接批准任何成片。
- `109f3b6` 已保存 `body-force-next-lever` post-clear 诊断 action。当前后续本地改动新增 `run_force_kind_scan.py`，用于可复现 force-kind 小范围映射。

关键限制：

- `body-force-main=8` 的旧直接输入尝试不能算 index 8 映射成功或失败；它只说明直接调用 `touch_Lever/touch_Reel` 没有消费 force flag。
- 后续 index mapping 必须在同一运行中捕获独立观察者的 `force_flag_set` 或等价真实游戏消费证据，再看 `runtime_sp_story_state.csv` / event code / CSL queue。
- ac7114-16 的最终 Bilibili 长片仍需关闭 BGM/bed 证据门：证明存在额外外层 BGM并加入，或证明官方外层对该 SP Story 无额外 BGM。

### 2026-07-03 断电恢复后的 force mapping 结果

ARM64 Gadget 已恢复，步骤为 root x86 frida-server、`reinject_gadget.py`、再 `adb forward tcp:27043 tcp:27043`。恢复后的可审计证据根：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence
```

已完成：

- 自然一转基线：`natural_baseline_one_spin_after_recovery_20260703`
  - 捕获普通一转音频、BGM helper、event-code 请求；
  - 未设置 force 时没有 `force_flag_set`。
- `body-force-main` 直接写入失败原因已明确：
  - 一转必须从 `body_state=1/body_mode=1` ready 状态开始；
  - `CSlotBody::START` 早期清理会清掉预先写入的 `body_force_main`。
- 新增 post-clear 诊断 action：

```powershell
python tools\frida_runtime_probe\force_selector_host.py body-force-next-lever --index <kind>
```

它用于 force kind 映射，不是最终投稿输出的批准机制。

验证结果：

- `force_index0_postclear_chain_20260703` 捕获到独立 observer 的
  `force_flag_set arg0=0`，证明诊断链路有效。
- `force_index8_postclear_probe_20260703` 捕获到
  `force_flag_set arg0=8 return=1`，并在该次运行映射到 `ac0922_001`
  (`0x31434e5a38404764`，声音 `31043`-`31061`)；后续 selector 校准中 kind 8
  进入普通 `ac0101`/`ac0102`/`ac9071`/`ac9920` 路线。两类结果都没有
  `C_ObjStageAT_SP_Story` 事件，所以 kind 8 只能作为非目标诊断路线，不能当成
  稳定 ac0922 selector，更不是 ac7114/ac7115/ac7116 目标。

新增自动扫描结论：

- 当前 MuMu 输入坐标必须按物理 `2160x3840` 使用：
  - 标题 `シミュレーション`：`1080 3000`
  - `ゲームスタート`：`600 2670`
  - 停轮：`880/1160/1440 2860`
- 新工具：

```powershell
python tools\frida_runtime_probe\run_force_kind_scan.py --candidates 3-7,9-19 --restart-each --duration 40 --out-dir D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\force_kind_scan_3_7_9_19_v2_20260703
```

- 无效样本目录：`force_kind_scan_2_7_9_19_20260703` 与
  `force_kind_scan_smoke_kind2_v2_20260703`，原因是当时没有处理标题页进入机台，未观测到
  `slot_pointer`/`slot_body_pointer`，不能作为阴性。
- 有效 evidence：
  - `force_kind_scan_smoke_20260703`：kind 1 有效，非目标；
  - `force_kind_scan_smoke_kind2_v3_20260703`：kind 2 有效，非目标；
  - `force_kind_scan_3_7_9_19_v2_20260703`：kind 3-7、9-19 有效，均非目标；
  - `force_index8_postclear_probe_20260703`：kind 8 曾命中 `ac0922_001`，后续校准
    又命中普通路线；均非目标。
- 结论：post-clear `body_force_main` kind `0..19` 没有一个进入
  `ac7114_001` / `ac7115_001` / `ac7115_013` / `ac7116_001`，且有效扫描中的
  `sp_story_state_count=0`。不要继续盲扫更大 kind 范围；当前 SP Story
  route 已推进为 `MSTCOMCBK()+0x2376 -> C_AnmBase+0x318` 加
  `SdGmData+0x788 -> MSTCOMCBK()+0x2378 -> C_AnmBase+0x31a ->
  C_ObjStageAT_SP_Story+0x34a`。目标已由 route-table 解码为
  `ac7114_001` stage `11` selector `1/2`、`ac7115_001` stage `12`
  selector `1/2/3/4`、`ac7115_013` stage `12` selector `13/14`、
  `ac7116_001` stage `13` selector `1/2`；下一步应优先查
  `runtime_rxcom_dir_flow.csv`，再结合 `runtime_gr_dir_prm_copy.csv` 和
  `runtime_anm_dir_data.csv` 找谁写 stage kind 与 selector，再做窄范围
  runtime probe。

### 2026-07-03 后续 Gadget 恢复与单会话 control 更新

后续 runtime 取证证明 27043 ARM64 Gadget 在当前 MuMu 状态下不适合让
observer 和 trigger 两个 host 进程同时 attach。`run_force_kind_scan.py`
先启动 combined CSL observer，再调用 `force_selector_host.py` 时，第二个连接
可能在 `enumerate_processes()` 直接失败：

```text
frida.TransportError: connection closed
```

新增/更新的持久证据目录：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\diagnose_gadget_after_transport_closed_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\gadget_reinject_after_app_restart_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\natural_bgm_backtrace_smoke_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\rxcom_force_kind8_backtrace_v2_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\single_session_force_kind8_control_v1_20260703
```

工具变化：

- `runtime_probe_host.py` 现在支持在同一 Gadget session 内同时加载 observer
  script 和 control script：

```powershell
python tools\frida_runtime_probe\runtime_probe_host.py `
  --script tools\frida_runtime_probe\csl_audio_queue_probe.js `
  --control-script tools\frida_runtime_probe\force_selector_probe.js `
  --control-sequence body_bet=1,body_bet=1,body_force_next_lever=8 `
  --out D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\<run>\observer_control_csl.jsonl `
  --duration 30 --quiet --no-unload
```

- `csl_audio_queue_probe.js` 已给 RxCom/SdGm route hook 和 BGM helper hook
  增加 backtrace 字段。
- `summarize_runtime_audio_capture.py` 已把 BGM `symbol`、`address`、参数和
  backtrace 导出到 `runtime_bgm_calls.csv`。

当前结果：

- `gadget_reinject_after_app_restart_20260703` 成功恢复 ARM64 Gadget：
  `ok=true`、`gadget_arch=arm64`、`gadget_sees_libGameProc=true`。
- `natural_bgm_backtrace_smoke_20260703` 捕获到最终 OpenSL queue sound id
  `8993` 和 `8998`，但 24 秒窗口内没有 BGM helper 行。这只是 smoke，
  不能证明目标 SP Story 原生无 BGM。
- `rxcom_force_kind8_backtrace_v2_20260703` 没有捕获 RxCom flow；该次 ready
  state 有效，但第二个 Frida 连接在触发前失败，因此只能算环境/控制失败，
  不能算 route 阴性。
- `single_session_force_kind8_control_v1_20260703` 证明“同一 JSONL 内 observer
  + control”可行，但 control 初始状态不是一转 ready：
  `body_state=0`、`body_mode=0`、`body_bet=0`。该 run 仅见 event code
  `0x43454f646b32615a`，`sp_story_state_count=0`、`rxcom_dir_flow_count=0`、
  `bgm_call_count=0`。它是工具链证明，不是 SP Story 证据。

下一步应在单会话 control run 内先证明状态达到
`body_state=1/body_mode=1/body_bet=3`，再触发 `body_force_next_lever=8`
或后续找到的真实 stage/selector 入口，并在同一 JSONL 中检查
`runtime_rxcom_dir_flow.csv`、`runtime_anm_dir_data.csv`、
`runtime_bgm_calls.csv` 和最终 CSL queue。

### 2026-07-03 静态 RxCom payload -> SP Story selector 链闭合

断电恢复后的静态扫描新增证据目录：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\static_mem_offsets_rx_chain_0ec_0ee_20260703
```

关键结论：

- `fnRxComDirInfo8` 从 RxCom payload 写入 SdGmData：
  - `payload[5] -> SdGmData+0x16e`
  - `payload[4] -> SdGmData+0x170`
- `fnRxComPreMdl` 继续复制：
  - `SdGmData+0x16e -> SdGmData+0xee`
  - `SdGmData+0x170 -> SdGmData+0xec`
  - `SdGmData+0xec -> SdGmData+0x318`
  - `SdGmData+0xee -> SdGmData+0x31a`
- `C_AnmBase::fnDataSetDir_DIR()` 再把
  `MSTCOMCBK()+0x2376/+0x2378` 复制到 `C_AnmBase+0x318/+0x31a`。

精确反汇编证据：

```text
fnRxComDirInfo8:
0x4486220  strh w20, [x0, #0x16e]  ; payload[5]
0x448622c  strh w20, [x0, #0x170]  ; payload[4]

fnRxComPreMdl:
0x44817fc  ldrh w19, [x0, #0x16e]
0x4481804  strh w19, [x0, #0xee]
0x448180c  ldrh w19, [x0, #0x170]
0x4481814  strh w19, [x0, #0xec]
0x4481d1c  ldrh w19, [x0, #0xec]
0x4481d24  strh w19, [x0, #0x318]
0x4481d2c  ldrh w19, [x0, #0xee]
0x4481d34  strh w19, [x0, #0x31a]
```

这进一步证明目标不是 `ac` 后缀数字、不是 CRI index，也不是继续盲扫
`body_force_main`。需要找的是让 `fnRxComDirInfo8` 收到目标 payload 的外层
调度路径：`payload[4]` 应产生 stage kind `11/12/13`，`payload[5]`
应产生 selector `1/2/3/4/13/14`。下一步 runtime backtrace 应优先抓
`fnRxComDirInfo8` 的 caller/dispatch，而不是扩大 force kind 范围。

### 2026-07-03 DirInfoTable / EventInfo 通用事件机制

`survey_aarch64_xrefs.py` 已扩展 `ADRP+ADD/LDR` PC-relative xref 扫描，
用于定位 GOT/global table 使用者。新增静态输出：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\static_xref_dirinfo_table_got_pc_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\static_xref_eventinfo_got_pc_20260703
```

通用机制：

- `DirInfoTable` 是 4640 字节 object，按 16 字节一项，对应 kind `0..0x121`。
- `C_DirInfoManager::fnGetEventCodeEtlt`：
  - 读取 `DirInfoTable`；
  - `entry = DirInfoTable + kind * 16`；
  - `entry+0` 指向 u16 网格；
  - `entry+8/+0xa` 是范围/维度检查；
  - 通过 `row` 与 `selector` 取 u16 `EventInfo` index；
  - `EventInfo + index * 24` 取最终 event code 指针。
- `C_DirInfoManager::fnGetActiveTrgEtlt` 与
  `fnGetActiveEventCodeEtlt` 复用同一表。
- `C_DirectionControllerBase::Macro_EVENT_PLAY` 也直接使用 `EventInfo`。

这回答了当前机制问题：游戏并不靠人为逐个 `ac` family 分类处理。它使用
`RxCom payload -> SdGmData -> kind/selector -> DirInfoTable -> EventInfo ->
event code` 的表驱动机制。我们的 pipeline 也应转向解析/复刻这条机制，而
不是视觉分类或手动逐个 family 处理。

### 2026-07-03 DirInfoTable / EventInfo 全局解码 v3

新增工具：

```text
tools/frida_runtime_probe/decode_dirinfo_event_tables.py
```

输出：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\dirinfo_event_table_decode_v3_20260703
```

关键结果：

- `DirInfoTable`: 290 entries。
- `EventInfo`: 9732 records。
- 应用 `.rela.dyn` 后所有 290 个 DirInfo grid pointer 均可解析。
- `route_cell_total=122028`，非零 `route_row_count=37266`。
- 已通过现有 manifest 反查 `926` 个 unique event code，覆盖 `3908` 条 route row。
- 产物包括：
  - `event_info_records.csv`
  - `dirinfo_entries.csv`
  - `dirinfo_event_routes.csv`
  - `resolved_dirinfo_event_routes.csv`
  - `resolved_scene_catalog.csv`
  - `base_scene_summary.csv`

重要命名修正：`DirInfoTable kind` 不是前面 SP Story 对象内的
`stage_kind_u16_at_0x318`。例如：

```text
ac7114 -> DirInfo kind 190
ac7115 -> DirInfo kind 191
ac7116 -> DirInfo kind 192
```

而 SP Story 对象内先前解析的 stage kind 是 `11/12/13`。后续文档和代码必须
显式区分 `dirinfo_kind` 与 `sp_story_stage_kind`，不能混用。

`resolved_scene_catalog.csv` 已按 `first_base_name, first_kind,
first_row_index, first_selector_raw` 排序，可作为同 base_name 长片候选顺序。
它只负责事件发现/排序；是否能进入 B 站投稿成片仍必须通过音频、字幕、BGM、
尾帧 hold、素材层排除等 runtime QA gate。

### 2026-07-03 断电后运行时恢复与 force190 负面验证

断电恢复后，MuMu 目标 `127.0.0.1:16384` 的实际输入坐标系是
`2160x3840`，截图会被拉成约 `1152x2048` 显示。因此标题页进入
シミュレーション应使用物理坐标约 `1080,3000`，不是截图坐标。

已恢复运行时：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\gadget_reinject_after_power_restore_20260703
```

结果：`gadget_arch=arm64`，`gadget_sees_libGameProc=true`。

控制状态与音频 hook 已验证：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\post_power_restore_bet3_20260703
```

3 次 bet 后状态达到 `body_state=1/body_mode=1/body_bet=3/credit=47`。
同次采集观察到 high-level BGM helper、event-code request、`sound_id=9002`
的最终 OpenSL queue chunk，说明断电后 runtime 音频链路和控制链路可用。

负面验证：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\force_dirinfo_kind190_probe_20260703
```

把 `DirInfoTable kind 190` 直接作为 `body_force_main`/force kind 使用是错误路径。
本次 `fnSetForceFlag(190,0)` 返回 `-1`，`fnGetForceFlagKind()` 返回 `0`，
随后脚本销毁且游戏退回 launcher。结论：`dirinfo_kind=190` 能用于事件表
发现/排序，但不能直接当 `body_force_main` force selector。该运行不是
ac7114 route negative，只是排除一个错误控制假设。

### 2026-07-03 story lottery 静态表与 BGM 负面/正面线索

新增工具：

```text
tools/frida_runtime_probe/disassemble_aarch64_functions.py
```

当前反汇编输出：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\static_disasm_story_dispatch_20260703
```

关键静态发现：

- `fnLot_OT_AT_StryKnd` 使用 `0x2f44406` 的 19 组静态表；每组 8 个 u16，
  写入 `SdGmData+0x1f72..0x1f80`。
- `fnLot_OT_AT_StryChara` 使用 `0x2f44536` 的 23 组静态表；每组 5 个 u16，
  写入 `SdGmData+0x1f94..0x1f9c`，并使用 `+0x1f9e` 标志。
- 表导出目录：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\static_story_lottery_tables_20260703
```

`csl_audio_queue_probe.js` 已扩展记录上述字段，并 hook：

```text
fnLot_OT_AT_StryKnd   -> lot_ot_at_stryknd
fnLot_OT_AT_StryChara -> lot_ot_at_strychara
```

hook 安装验证：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\story_lottery_hook_smoke_20260703
```

自然 spin 受控测试：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\natural_spin_story_lottery_probe_20260703
```

该测试没有使用 force kind，只执行 `set_debug=0`、3 次 bet、lever。结果：

- 游戏在 lever 后退回 launcher，control 路径仍不可靠；
- `lot_ot_at_stryknd/strychara` 本次没有触发；
- `fnReqSndEventCode` 触发 7 次，解析为 `ac0001_001`、`ac9010_060`、
  `ac9071_001`、`ac9100_001`、`ac9902_001`、`ac9903_001`、`ac9920_001`；
- `C_ObjNml::fnSndRequest_BGM_*` 相关 hook 每类出现 76 次；
- 最终捕获一个 OpenSL queue chunk：`sound_id=9002`，`265884` bytes。

结论：运行时确有 BGM/声音队列活动。此前渲染输出没有 BGM，不能再解释成
“游戏本身必然没有 BGM”；应优先视为抽音/混音/渲染 pipeline 丢失 BGM 或仅
抽取 voice/event audio。目标场景是否存在 event-specific BGM 仍需通过真实
SP Story 调度捕获证明。该自然 spin 测试是负面控制证据，不能用于成片验证。

测试后已恢复游戏到主界面并重新注入 Gadget：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\recover_after_natural_spin_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\restore_after_natural_spin_reinject_20260703
```

### 2026-07-04 轻量真实输入探针与 D 盘恢复策略

断电后 A: 的 2026-07-03 临时文件不应再被当作唯一证据源。当前恢复策略：

```text
D:\magia\MyProducts\casino  # durable immediate work root
A:\                         # RAM-disk scratch / restored 2026-06-29 backup
```

新增稳定 real-input observer：

```text
tools/frida_runtime_probe/lightweight_spin_audio_probe.js
```

并修正 `runtime_probe_host.py`：当 Frida script 已经 detach/unload 时，host
退出阶段的 `InvalidOperationError` 不再把可用 capture 标成失败。

不要再用重型 full probe 做真实转动观测：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\physical_input_spin_observe_20260704
```

该 run 的 crash log 首帧在
`libmagireco_gadget.so!libfrida-gadget-raw.so`，属于 hook/observer 诱发不稳定；
不是游戏 SP Story route 的负证据。

可继续使用的轻量成功 run：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_physical_bet_calibration_20260704
```

结论：

- lightweight probe 在真实 ADB tap 下稳定，游戏保持 foreground；
- 成功观察 START/STOP、RxComDirInfo8、RxComPreMdl、LotDirPreMdl；
- final queue 观察到 `sound_id=9002`、`60`、`61`；
- `fnReqSndEventCode` 解析到 `FL_UNIV_001`、`ac0001_001`、`ac9902_001`、
  `ac9010_060`、`ac9071_001`、`ac9100_001`、`ac9903_001`、`ac9920_001`
  和 `ac9071_002`；
- 本次普通转动没有触发 `fnLot_OT_AT_StryKnd/Chara` 或
  `C_ObjStageAT_SP_Story`；
- `fnRxComDirInfo8` payload `[4]`、`[5]`、`[6]` 仍为 0。

因此该 run 证明的是“轻量观测路线可靠”和“运行时 audio queue 确实存在”，不是
ac7114/ac7115/ac7116 BGM 或成片正确性证明。下一步仍是找到真实触发
`payload[4]=11/12/13` 与 `payload[5]=1/2/3/4/13/14` 的上游调度。

当前坐标校准：

```text
title simulation: 约 1080,3000
game start:       约 600,2670
lever:            约 300,2680
stop buttons:     约 830,2700 / 1080,2700 / 1320,2700
BET candidate:    约 620,2475 到 620,2520
```

旧 stop `y=2860` 在按钮下方，不要继续使用。

### 2026-07-04 SdGmData story-lottery dispatch proof

新增机制报告：

```text
docs/research/2026-07-04-sdgm-lottery-dispatch-route.md
```

新增可审计证据：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\static_mem_offsets_sdgm_lottery_source_20260704
D:\magia\MyProducts\casino\runtime_recovery_20260704\static_disasm_sdgm_lottery_source_candidates_20260704
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_force358_on_lotdirstart_real_input_20260704
```

当前闭合结论：

- `fnLotDirGmStart` 读取 `SdGmData+0x358`。
- 当 `SdGmData+0x358=8` 时，`fnLotDirGmStart` 写
  `SdGmData+0x13be=16`。
- `fnLotOther_AfterGetParam` 在 `+0x13be=16` 分支调用
  `fnLot_OT_AT_StryKnd`、`fnLot_OT_AT_SpStryKnd` 和
  `fnLot_OT_AT_StryChara`。
- 运行时 one-shot 测试在 `fnLotDirGmStart` 入口写 `+0x358=8` 后，实际观测
  到 `+0x13be=16`，并触发 `lot_ot_at_stryknd` 与
  `lot_ot_at_strychara` hook。
- 基址感知扫描进一步证明 `+0x358` 的上游链是
  `fnRxComDirInfo3 payload[6] -> SdGmData+0x130 -> +0x0a8 -> +0x184 ->
  +0x358`。因此当前应寻找能让 `fnRxComDirInfo3 payload[6]=8` 的自然条件。

新增上游证据：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\static_sdgm_base_refs_lottery_source_20260704
D:\magia\MyProducts\casino\runtime_recovery_20260704\static_sdgm_base_refs_lottery_source_upstream_130_20260704
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_natural_dirinfo3_chain_real_input_20260704
```

普通观测 run 中 `fnRxComDirInfo3 payload=[29,1,1,0,0,8,0,19]`，其中
`payload[6]=0`，所以 `+0x358` 仍为 0；`payload[5]=8` 不是这条 lottery
dispatch 字段。

后续 ID401 dispatcher 取证进一步澄清 payload 顺序：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_id401_task_entry_real_input_20260704
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_id401_task_entry_real_input_20260704\summary_light_id401_task_entry.json
D:\magia\MyProducts\casino\runtime_recovery_20260704\static_disasm_id401_access_subprocess_20260704
D:\magia\MyProducts\casino\runtime_recovery_20260704\static_disasm_id401_pio_task_table_20260704
```

`ID401::accessSubProcess(unsigned char*)` 读取 `packet[0] & 0x7f`，通过
`fnPioTaskTbl_SearchTblApp` 查 runtime PIO task table，然后对原始 8 字节执行
`rev64` 再派发给 `fnRxCom*` callback。因此 Frida 在 `fnRxComDirInfo3`
hook 里看到的是 byte-reversed callback payload，不是原始 packet。当前真实输入
观察到：

```text
raw packet        = [19, 0, 8, 0, 0, 1, 1, 29]
packet_id         = 19
callback0         = fnRxComDirInfo3
callback payload  = [29, 1, 1, 0, 0, 8, 0, 19]
caller            = CSlotBody::analysPacket()+0x2b4
```

所以 `fnRxComDirInfo3 callback payload[6]=8` 等价于更上游的
`ID401 packet id 19 raw_packet[1]=8`。当前普通包是 `raw_packet[1]=0`，其
`8` 位于 raw byte 2 / callback `payload[5]`，不会触发这条
`SdGmData+0x130 -> +0x358` lottery route。下一步应追
`CSlotBody::analysPacket()` / `ID401::accessSubProcess()` 上游 packet producer，
而不是继续扩大 force kind 或按 ac 后缀猜测。

仍未闭合：

- 自然运行时什么条件产生 `fnRxComDirInfo3 payload[6]=8`；
- 等价地，什么上游 producer 产生 `packet_id=19 && raw_packet[1]=8`；
- lottery 输出如何继续创建具体 SP Story object 和目标 ac；
- ac7114/ac7115/ac7116 的自然 outer-flow 额外 BGM/bed 是否存在。

注意：全局 raw `+0x358` offset 扫描会混入
`C_ObjStageAT_SP_Story+0x358` 这类非 SdGmData 字段。不要把 raw write hit
当成 SdGmData 写入源，除非基址被证明来自 `fnGetAddrSdGmData()`。

## 2026-07-04 追加：ID401/LC701A 上游 byte-builder 进展

本轮在正确分支 `codex/corrected-runtime-pipeline` 上继续推进，不使用 A:
作为证据源。新增结论写入：

```text
docs/research/2026-07-04-id401-command-buffer-source.md
```

关键变化：

- 静态反汇编工具已修正 AArch64 PLT 解析。此前 nearest-symbol 方式会把
  PLT 调用误标为无关符号；现在通过 `.rela.plt/.dynsym/.dynstr` 解析真实
  import 名称。
- `LC701A_SLOT::USER_LABEL_WORK()` 被确认是基于 `this+0x20` 的 LC701A PC
  dispatch，不是按 ac 后缀或静态列表选择素材。
- PC `0x58a`、`0x1156` 以及 `SET_BANKBUFFER()` 进入同一个 enqueue block：
  从 `this+0xf298` / `this+0xf0fe` 把 staging command bytes 复制到
  `this+0x200ee` queue，再清空 staging。
- 重新汇总完整 spin JSONL 后，`USER_LABEL_WORK` enter/leave 内部没有
  staging 变化；变化发生在连续 enter snapshot 之间，说明 packet 是由 LC701A
  VM/helper 执行逐字节构建。
- 普通 DirInfo3 包 `[19, 0, 8, 0, 0, 1, 1, 29]` 的构建已能定位到 byte
  sequence：byte 48 开新包，byte 50 写入 `raw[2]=8`，后续 byte 53/54/55
  写入 `1/1/29`。这仍然不是目标；目标仍是 `packet_id=19 &&
  raw_packet[1]=8`。

新增/更新工具：

```text
tools/frida_runtime_probe/survey_aarch64_xrefs.py
tools/frida_runtime_probe/disassemble_aarch64_functions.py
tools/frida_runtime_probe/summarize_lightweight_spin_probe.py
tools/frida_runtime_probe/lightweight_spin_audio_probe.js
```

新的 `lightweight_spin_audio_probe.js` 追加 LC701A command-state-change hook：
只在 `_OUTI/_OUTIC/_IN/_INI/_INIC/_JP/_RET/_RETEX/ASM_0xA7/ASM_0xAF/ASM_0xF8/
SET_ENC_SUBFUNC/RESET_ENC_SUBFUNC` 导致 ID401 staging 或 queue signature
变化时输出事件。下一次自然 spin 应使用这个低噪声 hook 直接证明是谁写入
DirInfo3 `raw_packet[1]` 或 `raw_packet[2]`。

对最终目标的影响：

- 人工逐个视觉分类不是可扩展路线，已继续转向游戏自身 packet/scheduler
  机制。
- 距离最终 Bilibili 长片仍差一层关键闭环：自然运行时从 LC701A packet
  producer 到 SP Story stage/selector，再到最终 OpenSL 声音队列和可能的
  BGM/bed。
- 已通过用户听检的 ac7114/ac7115/ac7116 语音/字幕结果仍可保留为强样本，
  但最终长片 promotion 仍需 BGM/outer-flow 证据门。

## 2026-07-04 追加：LC701A ordinary opcode writer 识别

后续 ready-state 物理输入捕获：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_lc701a_state_change_from_ready_20260704
```

结论：

- 从真正 ready 状态执行 lever/stop 后，捕获到 1436 条 packet observation、
  10 种 raw packet、10 次 LC701A staging 变化、0 个 hook 错误。
- 该 run 没有 DirInfo3，也没有 target candidate；它不是目标故事证据。
- 它证明普通 packet byte-builder 的 PC 模式与先前完整 spin 一致：
  `101/102/113/114`，即十六进制 `0x65/0x66/0x71/0x72`。

新增静态反汇编：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\static_disasm_lc701a_packet_builder_opcodes_20260704
```

关键识别：

- `CLC701A::ASM_0x71()` 和 `ASM_0x72()` 是 VM RAM 写入 opcode；
  当地址 `>=0x4000` 时写 `this+0x88+addr`。
- `LC701A_SLOT+0xf298` staging 对应 VM RAM 地址 `0xf210`，因此
  `ASM_0x71/0x72` 是 packet staging byte 的主要写入候选。
- `ASM_0x65/0x66` 是相邻读/组合 helper，同样加入低噪声 hook 以还原 byte
  source。

工具更新：

```text
tools/frida_runtime_probe/lightweight_spin_audio_probe.js
```

现在额外 hook：

```text
ID401::CLC701A::ASM_0x65()
ID401::CLC701A::ASM_0x66()
ID401::CLC701A::ASM_0x71()
ID401::CLC701A::ASM_0x72()
```

下一次有效 ready-state 捕获应验证这些 opcode hook 是否直接产生
`*_command_state_change` 事件。若出现 DirInfo3，则重点看 `raw_packet[1]`
是否由 `ASM_0x71/0x72` 写入。

## 2026-07-04 追加：全 opcode hook 修正 packet writer

上一个小节的 `ASM_0x65/0x66/0x71/0x72` 解释已被更新结果修正：这些数值来自
LC701A 程序计数器，不应直接当作 opcode helper 编号。当前正确结论如下。

`lightweight_spin_audio_probe.js` 已改为自动 hook 全部
`ID401::CLC701A::ASM_0x00()` 到 `ASM_0xff()`，仍然只在 ID401 staging 或
queue signature 实际变化时输出 `*_command_state_change`，避免回到高噪声观测。

最新有效物理输入捕获：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_lc701a_full_opcode_bet_lever_corrected_stops_20260704
```

写入本节时的当前 live 状态为：

```text
ADB device: emulator-5554
game PID:   5294
Frida:      127.0.0.1:27042 / 27043 listening
```

若 MuMu 或 app 再次重启，必须重新确认 PID 与 Gadget，不得沿用旧 PID。

v2 汇总输出：

```text
summary_light_lc701a_full_opcode_bet_lever_corrected_stops_v2.json
summary_light_lc701a_full_opcode_bet_lever_corrected_stops_v2_command_state_changes.csv
summary_light_lc701a_full_opcode_bet_lever_corrected_stops_v2_lc701a_enter_sequence.csv
summary_light_lc701a_full_opcode_bet_lever_corrected_stops_v2_packets.csv
```

摘要：

```text
packet_count=155
unique_packet_count=6
candidate_count=0
dirinfo3_packet_count=0
bgm_event_count=468
slot_event_count=1096
hook_error_count=0
command_state_change_count=7
command_state_change_kind_counts:
  lc701a_opcode_0x7e_command_state_change = 5
  lc701a_opcode_0x77_command_state_change = 2
```

`command_state_changes.csv` 显示普通 packet 的 staging 写入链条：

```text
lc701a_opcode_0x77: pending_len 0 -> 8
lc701a_opcode_0x7e: byte 0 -> 4
lc701a_opcode_0x7e: byte 1 -> 1
lc701a_opcode_0x7e: byte 2 -> 3
lc701a_opcode_0x7e: byte 3 -> 156
lc701a_opcode_0x7e: byte 4 -> 240
lc701a_opcode_0x77: byte 7 -> 148
```

新增静态反汇编：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\static_disasm_lc701a_packet_writer_opcodes_77_7e_20260704
```

当前解释：

- `ASM_0x77` 是单字节 VM RAM store，本次负责创建/维持 8 字节 pending
  staging，并写入最后一个 tail/check byte。
- `ASM_0x7e` 是一字节 VM RAM copy，本次负责把 packet body 字节复制进
  staging。
- 这不是目标 SP Story 证据，因为本次没有 DirInfo3，也没有
  `packet_id=19 && raw_packet[1]=8`。
- 但它已经证明：追踪路线应是 LC701A VM opcode 写包机制，而不是手工按
  `ac` family 分类或按视觉猜测。

下一步机制目标不变但更精确：

```text
在自然运行中捕获 packet_id=19 的构建过程，
确认 raw_packet[1] 何时、由哪个 opcode 写成 8，
再把同一 run 接到 SP Story stage/selector 与最终 OpenSL queue/BGM。
```

## 2026-07-04 追加：DirInfo3 普通包已逐字节归因

在当前 live PID `5294` 下，从 stopped/ready 画面执行 BET x3、lever、三 stop，
使用全 opcode 低噪声 hook 捕获：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_lc701a_full_opcode_spinscan_20260704_01
```

汇总结果：

```text
observer_bytes=6671629
packet_count=10034
unique_packet_count=29
dirinfo3_packet_count=815
candidate_count=0
hook_error_count=0
bgm_event_count=234
queue_event_count=1
slot_event_count=2338
lc701a_enter_sequence_changed_count=25
command_state_change_count=37
command_state_change_kind_counts:
  lc701a_opcode_0x7e_command_state_change=17
  lc701a_opcode_0x77_command_state_change=20
```

本次普通 DirInfo3 为：

```text
raw packet       [19,0,6,0,0,1,0,26]
callback payload [26,0,1,0,0,6,0,19]
```

仍不是目标：

```text
raw_packet[1]=0
raw_packet[2]=6
candidate_count=0
```

但 `command_state_changes.csv` 已经把 DirInfo3 packet 构建归因到 opcode：

```text
line 5283  ASM_0x7e  48:->19;49:->0;50:->0;51:->0;52:->0;53:->0;54:->0;55:->0
line 5288  ASM_0x7e  50:0->6
line 5295  ASM_0x7e  53:0->1
line 5320  ASM_0x77  55:0->26
```

同一 run 的 RxCom 行确认：

```text
rxcom_dirinfo3_enter payload = 26 0 1 0 0 6 0 19
SdGmData+0x130/+0x0a8/+0x184/+0x358/+0x13be 全部保持 0
```

同一 run 仍有外层 slot sound 活动：

```text
BGM helper rows=234
final queue: sound_id=60, 286788 bytes
```

下一步应增强 opcode 专用采样，而不是继续盲跑：

```text
ASM_0x7e: 记录 src/dst VM address、count、source byte、dest byte
ASM_0x77: 记录 dst VM address、register byte source、dest byte
```

目标是在出现 `packet_id=19` 时知道 raw byte 1 和 raw byte 2 分别从哪里复制/
写入，进而定位自然 SP Story scheduler 条件。

## 2026-07-04 追加：opcode source/destination 采样已验证

`lightweight_spin_audio_probe.js` 现在在 `state_before/state_after` 中记录
LC701A opcode 相关寄存器、VM 地址和源/目标字节；`summarize_lightweight_spin_probe.py`
会把这些字段导出到 `command_state_changes.csv`。

新增列包括：

```text
lc701a_addr06_before/after
lc701a_addr08_before/after
asm7e_dst_addr_before/after
asm7e_src_addr_before/after
asm7e_count_before/after
asm7e_src_byte_before/after
asm7e_dst_byte_before/after
asm77_dst_addr_before/after
asm77_src_reg_before/after
asm77_dst_byte_before/after
```

验证 run：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_lc701a_opcode_addr_spinscan_20260704_01
```

摘要：

```text
packet_count=157
unique_packet_count=7
dirinfo3_packet_count=0
candidate_count=0
hook_error_count=0
bgm_event_count=527
queue_event_count=1
slot_event_count=3830
command_state_change_count=8
command_state_change_kind_counts:
  lc701a_opcode_0x7e_command_state_change=6
  lc701a_opcode_0x77_command_state_change=2
```

该 run 没有 DirInfo3，不是目标证据；但它证明地址采样可用：

```text
ASM_0x7e src 0xfff3 -> dst 0xf210, byte 4
ASM_0x7e src 0xfff4 -> dst 0xf211, byte 1
ASM_0x7e src 0xfff5 -> dst 0xf212, byte 3
ASM_0x7e src 0xfff6 -> dst 0xf213, byte 156
ASM_0x7e src 0xfff7 -> dst 0xf214, byte 240
ASM_0x7e src 0xfff8 -> dst 0xf215, byte 1
ASM_0x77 reg byte 149 -> dst 0xf217
```

下一步应使用同一增强 probe 捕获包含 DirInfo3 的结果阶段，以确定
`raw_packet[1]` 对应 staging `0xf211` 从哪个 VM source address 复制而来，
并比较 ordinary `raw[1]=0` 与目标 `raw[1]=8` 的上游条件。

## 2026-07-04 追加：DirInfo3 source address 已进入可追踪状态

增强 source/destination probe 随后命中 ordinary DirInfo3：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_lc701a_opcode_addr_dirinfo3_try_20260704_02
```

摘要：

```text
observer_bytes=10755212
packet_count=10034
unique_packet_count=29
dirinfo3_packet_count=815
candidate_count=0
hook_error_count=0
bgm_event_count=402
queue_event_count=1
slot_event_count=3988
command_state_change_count=37
```

普通 DirInfo3：

```text
raw packet       [19,0,6,0,0,1,0,26]
callback payload [26,0,1,0,0,6,0,19]
```

source address 归因：

```text
raw[0] 19: ASM_0x7e staging 0xf240 <- source 0xffef
raw[2]  6: ASM_0x7e staging 0xf242 <- source 0xfff1
raw[5]  1: ASM_0x7e staging 0xf245 <- source 0xfff4
raw[7] 26: ASM_0x77 staging 0xf247 <- register byte
```

`raw[1]` 没有出现在 change-only 表中，因为普通值为 `0`，写 0 到 0 不会改变
staging signature。为解决这个盲区，`lightweight_spin_audio_probe.js` 现在新增
显式 `*_staging_write` event：只要 `ASM_0x7e/0x77` 写入 command staging
VM 范围，就输出一行，即便字节没有变化。

`summarize_lightweight_spin_probe.py` 新增：

```text
summary_<run>_opcode_staging_writes.csv
```

并加入十六进制地址列：

```text
dst_addr_hex
src_addr_hex
packet_offset
packet_byte_index
is_dirinfo3_raw_byte1
is_dirinfo3_raw_byte2
```

验证 run：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_lc701a_staging_write_dirinfo3_try_20260704_01
```

该验证 run 未进入 DirInfo3，但 v2 CSV 已证明 staging write 表工作正常：

```text
0xf210 <- 0xfff3 byte 4
0xf211 <- 0xfff4 byte 1
0xf212 <- 0xfff5 byte 3
0xf213 <- 0xfff6 byte 156
0xf214 <- 0xfff7 byte 240
0xf215 <- 0xfff8 byte 1
0xf216 <- 0xfff9 byte 0
0xf217 <- ASM_0x77 register byte
```

下一步目标更具体：

```text
再次捕获包含 DirInfo3 的 result window；
在 opcode_staging_writes.csv 中过滤 is_dirinfo3_raw_byte1=True；
确认 ordinary raw[1]=0 的 source address；
再寻找什么状态使该 source byte 变成目标值 8。
```

## 2026-07-04 追加：DirInfo3 raw[1] source address 闭合到 0xfff0

`opcode_staging_writes.csv` 已在下一次完整 result-window run 中命中 DirInfo3：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_lc701a_staging_write_dirinfo3_try_20260704_02
```

关键摘要：

```text
observer_bytes=11101512
packet_count=10034
dirinfo3_packet_count=815
candidate_count=0
hook_error_count=0
opcode_staging_write_count=96
opcode_staging_write_dirinfo3_byte1_count=1
opcode_staging_write_dirinfo3_byte2_count=1
```

普通 DirInfo3 的完整 source -> staging 映射：

```text
raw[0] 19: 0xf240 <- 0xffef
raw[1]  0: 0xf241 <- 0xfff0
raw[2]  6: 0xf242 <- 0xfff1
raw[3]  0: 0xf243 <- 0xfff2
raw[4]  0: 0xf244 <- 0xfff3
raw[5]  1: 0xf245 <- 0xfff4
raw[6]  0: 0xf246 <- 0xfff5
raw[7] 26: 0xf247 <- ASM_0x77 register byte
```

因此目标条件已经从 packet 级进一步收窄为：

```text
在 packet id 19 拷贝时，LC701A VM source 0xfff0 必须等于 8。
```

随后新增 source-window signature：

```text
id401_packet_source_watch_bytes_at_0xffe0
```

该 signature 被加入 command-state signature，所以任意 opcode 改写
`0xffe0..0xffff` 都会触发 `*_command_state_change`，并在 CSV 导出
`source_watch_changed_bytes`。

验证 run：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_lc701a_source_watch_full_spin_20260704_01
```

未命中 DirInfo3，但已证明 source-window 追踪能定位 `0xfff0/0xfff1` writer：

```text
ASM_0x48: 0xfff0 32->86, 0xfff1 17->0
ASM_0x4a: 0xfff0 86->91
ASM_0xd9: 0xfff0 91->16, 0xfff1 0->242
```

静态反汇编输出：

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\static_disasm_lc701a_source_watch_opcode_48_20260704
D:\magia\MyProducts\casino\runtime_recovery_20260704\static_disasm_lc701a_source_watch_opcode_4a_20260704
D:\magia\MyProducts\casino\runtime_recovery_20260704\static_disasm_lc701a_source_watch_opcode_d9_20260704
```

解释：

- `ASM_0x48` / `ASM_0x4a` 使用 `this+0x0e` 作为 stack pointer，向
  `this+0x88+stack` 写入两字节 PC/control 派生值，并更新 `this+0x20`。
- `ASM_0xd9` 同样向 stack/source 区写入两字节，但来源是 `this+0x06` 的 u16。

下一步最短路径：

```text
在同一 JSONL 内同时捕获：
1. source_watch_changed_bytes 修改 0xfff0；
2. 后续 DirInfo3 raw[1] staging write 读取 0xfff0；
3. 若 0xfff0=8，则继续追 RxCom/SdGmData/SP Story/BGM。
```
