> 本设计分册提取自 `docs/09_新场景与任务设计.md`（扩展轮，评审修订版）；四判据、与初版关系、验收要点以该总纲为准。

## 场景六 `shelf_picking` 仓储分拣站

**世界**:小型仓库拣选工位:三层层板货架靠墙,近处地面拣选篮,最深处小型传送带端部。任务图差异化标记:**双 background 监控**(CONV 端部 + GREEN 标记箱)+ 同深度不同角色的对照(RED 与 BLUE 同在二层,一 current 一 next/neutral——角色与深度解耦,留作对照实验条件)。

**视点与深度**:`camera_position_m=[0.35,-1.15,1.05]`,`camera_look_at_m=[0,0.45,0.6]`。
| 层 | 对象 | 位置(y,z) | 沿视轴距离 | role / depth | N/σ 倾向 |
|---|---|---|---|---|---|
| 近 | BASKET 拣选篮(放置锚点) | y≈-0.35, z≈0.02 | ≈1.0m | 锚点对象 | — |
| 中 | RED 二层包裹 | y≈+0.35, z≈0.75 | ≈1.7m | current / precise | 高 N,小 σ |
| 中 | BLUE 一层周转箱 | y≈+0.35, z≈0.45 | ≈1.6m | next / **neutral** | 中 N,中 σ |
| 远 | CONV 传送带端部 | y≈+1.35 | ≈2.6m | background / persistent | 低 N,大 σ |
| 远 | GREEN 端部标记箱 | y≈+1.30 | ≈2.55m | background / persistent | 低 N,大 σ |

GREEN 为传送带端部**静止标记箱**(场景对象位姿静态,"补货是否到达"由查看端部状态判断,不声明运动行为)。

**任务脚本**:
- 初始指令:`把第二层的红色包裹 RED 放进拣选篮 BASKET,然后翻看蓝箱 BLUE 背面的面单,同时留意传送带 CONV 端部有没有绿箱 GREEN 到位。`
- 打断:`先看 BLUE 的面单,包裹的事保留。`
- 扩展测试输入:

| 输入 | 检查点 |
|---|---|
| 把那个箱子翻过来 | RED/BLUE/GREEN 三箱在清单 → clarify |
| 把 RED 挪过去 | 目标不明(BASKET?CONV?)→ clarify |
| RED 先别放,蓝箱面单要紧 | 顺序对调,interrupt 语义 |
| 把 BASKET 翻过来看 | BASKET 无 inspect_back → 校验拒绝 |
| 绿箱到了先处理绿箱 | GREEN 变 current;原任务挂起 |
| 快速连发两条 | epoch 竞争,仅最新可提交 |

**为什么强契合**:1.7m 纵深上"低头放包裹 + 抬眼盯补货"是最典型的近操作/远监控注意力冲突(1.0m vs 2.6m 调焦差);双 background 是五场景中唯一的"双远层常驻"结构。RED/BLUE 同深度不同角色把"任务角色"与"物理深度"解耦,直接支撑论文的变量分离论证。颜色+层位指代、双任务并行超出规则解析器。BLUE 面单为径向面(箱体贴 +Y 侧),转台式查看成立。

**交互对象**:
| id | label | capabilities | anchors | description |
|---|---|---|---|---|
| RED | 红色包裹 | point, assemble | — | 二层标准件包裹 |
| BLUE | 蓝色周转箱 | point, rotate, inspect_back | — | +Y 侧贴发货面单 |
| BASKET | 拣选篮 | point | placement=[0,-0.0198,0.2525](pose 世界位 [0,-0.35,0.02];重制藤篮,锚点高于篮口 17mm) | 软底拣选篮 |
| CONV | 传送带端部 | point, wait | — | 到位指示灯在端部 |
| GREEN | 端部绿箱 | point, wait | — | 补货标记箱(静止) |

**环境**:三层层板货架(PolyHaven `steel_frame_shelves_02` 骨架+程序化层板)、`cardboard_box_01`/`plastic_crate_01`/`plastic_crate_02`/`wooden_crate_02`/`Barrel_02`/`cement_bag` 堆货、`hand_truck`、程序化传送带、`concrete_floor_worn_001` 地面。`render_hints`:ortho_scale≈2.0,grid_extent≈2.5,cue_scale=1.0,label_offset=0.12。

---
