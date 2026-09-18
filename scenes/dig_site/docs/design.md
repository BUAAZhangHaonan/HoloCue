> 本设计分册提取自 `docs/09_新场景与任务设计.md`（扩展轮，评审修订版）；四判据、与初版关系、验收要点以该总纲为准。

## 场景八 `dig_site` 考古探方发掘

**世界**:田野考古探方(trench):1.5m 见方、深 0.5m,四壁分层土色(表土/夯土/文化层),坑内陶片与骨化石半埋出露,坑外北侧全站仪持续锁定测站。任务图差异化标记:current 是**查背面**(非插入类),含 neutral 档使用。

**视点与深度(视轴从坑口上缘俯入坑内)**:`camera_position_m=[1.35,-1.35,1.05]`,`camera_look_at_m=[-0.494,0.848,0.173]`(as-built,重瞄准以同时容纳坑体与全站仪;ortho 3.81)。
| 层 | 对象 | 位置 | 沿视轴距离 | role / depth | N/σ 倾向 |
|---|---|---|---|---|---|
| 坑内中层 | POT3 陶片翻转查内壁 | 坑南壁 z≈-0.25 | ≈2.0m | current / precise | 高 N,小 σ |
| 坑内深层 | FLAG→BONE 旁插旗 | 坑底 z≈-0.45 | ≈2.3m | next / persistent | 中 N,大 σ |
| 坑外 | STAY 全站仪 | y≈+1.2, z≈0.2 | ≈3.1m | background / persistent | 低 N,大 σ |
| 工具 | TROWEL 手铲摆放 | 坑口 z≈0 | ≈1.8m | 扩展用 / **neutral** | 中 N,中 σ |

**任务脚本**:
- 初始指令:`把 3 号陶片 POT3 翻过来看内壁刻纹,然后在骨化石 BONE 旁边插红色标记旗 FLAG,坑边全站仪 STAY 保持锁定别碰。`
- 打断:`先插旗,陶片的事保留。`
- 扩展测试输入:

| 输入 | 检查点 |
|---|---|
| 把那个陶片翻过来 | POT1/POT2/POT3 均在清单 → clarify |
| 把旗插那边 | 放置锚点仅 BONE 一处,"那边"无法解析 → clarify |
| 把手铲顺时针转 90 度放好 | TROWEL rotate,角度显式 -90,neutral 档 |
| 把 STAY 挪过来 | STAY 无 insert/assemble 且"保持锁定"语境 → clarify 确认意图 |
| 翻看 BONE 的底面 | BONE 无 inspect_back → 校验拒绝 |
| 骨化石动了,先停下 | 暂停语义,状态保存 |

**为什么强契合**:探方是"深度即地层"的天然结构——陶片层位、坑底插旗点、坑外仪器分属三个调焦面(2.0/2.3/3.1m),地层学语境让焦深分层有语义而不只是布局;平面截图无法表达埋藏深度。考古口语指代("那片""旁边""那边")与多陶片歧义是 LLM 的典型职责;"保持锁定别碰"输出 background persistent。FLAG 目标姿态继承 BONE 局部系(BONE 姿态为单位四元数、FLAG 局部 +Z 沿杆向,见 projection.py 契约),旗落在坑底站立。

**交互对象**:
| id | label | capabilities | anchors | description |
|---|---|---|---|---|
| POT3 | 3 号陶片 | point, inspect_back | — | 直立嵌于南壁,内壁有绳纹刻痕 |
| FLAG | 红色标记旗 | point, assemble | — | 30cm 旗杆,局部 +Z 沿杆、尖头朝上 |
| BONE | 骨化石 | point | placement=[0,-0.08,0.02](pose 世界位 [0.18,-0.1,-0.45];-Y 为北侧) | 出露长骨,旗插其北侧 |
| STAY | 全站仪 | point, wait | — | 测站锁定,镜头朝探方 |
| POT1 | 1 号陶片 | point | — | 消歧用,仅指认 |
| POT2 | 2 号陶片 | point | — | 消歧用,仅指认 |
| TROWEL | 手铲 | point, rotate | — | 刃口朝向与柄线对齐 |

**环境**:探方坑体(细分面+噪声位移+顶点色分层,PolyHaven `excavated_soil_wall` 纹理增强)、坑口土堆(`dirt`/`gravelly_sand`)、`trowel_01`(TROWEL 外观基准)、`rusted_spade_01`、毛刷/卷尺(程序化)、`hessian_230` 麻布沙袋、`wooden_crate_01` 文物箱、`stone_01`/`rock_07` 点缀、程序化全站仪+三脚架、`ceramic_pot` 文物箱内整罐。`render_hints`:ortho_scale≈2.1,grid_extent≈2.5,cue_scale=1.0,label_offset=0.25(标签抬出坑口)。

---

## 状态注记（2026-09-18）

scene_agent/requirements.md 的真实性判据将本场景标记为"判定猎奇、待替换"；本轮套件化整理维持其官方链地位不变，后续如启用替换场景，按 `scenes/_template/KIT_CHECKLIST.md` 走全流程后移除本套件。
