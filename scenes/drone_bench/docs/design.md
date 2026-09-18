> 本设计分册提取自 `docs/09_新场景与任务设计.md`（扩展轮，评审修订版）；四判据、与初版关系、验收要点以该总纲为准。

## 场景五 `drone_bench` 无人机检修台

**世界**:消费级四旋翼维修台,1.6m 进深工作台:近端零件盒、中段无人机机身(仰放,腹部电池仓朝上)、远端台式电压表。任务图差异化标记:**双 precise 连续步**(插入+带角度旋转)+ 遮挡查背面 + 远层读数监控。

**视点与深度**:`camera_position_m=[0.55,-0.95,0.62]`,`camera_look_at_m=[0,0.05,0.12]`。
| 层 | 对象 | 位置(y,z) | 沿视轴距离 | role / depth | N/σ 倾向 |
|---|---|---|---|---|---|
| 近 | 零件盒(布景/交互 PARTS 见环境) | y≈-0.45 | ≈0.9m | — | — |
| 中近 | BAT→BAY 电池插入 | y≈0.05, z≈0.10 | ≈1.35m | current / precise | 高 N,小 σ |
| 中 | GUARD 护罩旋转 30°(顺时针,fixture 记 -30) | y≈0.05, z≈0.16 | ≈1.35m | next / precise | 中高 N,小 σ |
| 中 | M3 内侧减震垫(被机臂遮挡) | x≈-0.22, y≈0.22 | ≈1.5m | next / persistent | 中 N,大 σ |
| 远 | VOLTMETER 读数 | y≈+0.60 | ≈1.9m | background / persistent | 低 N,大 σ |

**任务脚本**:
- 初始指令:`把电池 BAT 插进机身电池仓 BAY,顺时针拧紧固定护罩 GUARD 30 度,再检查左后电机 M3 朝机身一侧的减震垫,电压表 VOLTMETER 全程盯着。`
- 打断:`先别装电池,看看 M3 的减震垫,装电池的事保留。`
- 扩展测试输入:

| 输入 | 检查点 |
|---|---|
| 把那个电机翻过来看看 | M1/M2/M3/M4 四个电机均在交互清单 → 指代不明,clarify |
| 把护罩拧一下 | 有 rotate 缺角度 → clarify |
| 把 BAT 再插深一点 | 锚点终点唯一 → interrupt 按既有 BAY 锚点演示 |
| 把桨叶拧下来 | 桨叶为环境对象不在清单 → 对象不存在,clarify 或拒绝 |
| 盯着电压表别看别的了 | VOLTMETER 变 current/wait;旧任务保留挂起 |

**为什么强契合**:装电池/拧护罩时电压表读数在另一调焦面持续变化(1.35m vs 1.9m);双 precise 步骤连续切换是"精确焦深提示"最密集的序列。M3 减震垫在电机朝机身一侧的径向面上,被机臂与桨叶遮挡,转台式 ghost 查看。"顺时针 30 度"显式角度、"左后"空间指代、四电机消歧,超出规则模板能力。

**交互对象**:
| id | label | capabilities | anchors | description |
|---|---|---|---|---|
| BAT | 智能电池 | point, insert | — | 黑色电池,沿把手方向插入 |
| BAY | 电池仓 | point | insertion=[0,0,-0.0185](pose 世界位 [0.02,0,0.148];BAT 齐平满插,86% 入仓) | 机身腹部卡扣仓 |
| GUARD | 电池护罩 | point, rotate | — | 顶部白色刻线为角度指示 |
| M1 | 前左电机 | point | — | 消歧用,仅指认 |
| M2 | 前右电机 | point | — | 消歧用,仅指认 |
| M3 | 左后电机 | point, inspect_back | — | 朝机身一侧径向面上有橙色减震垫 |
| M4 | 右后电机 | point | — | 消歧用,仅指认 |
| VOLTMETER | 台式电压表 | point, wait | — | 数码管读数,过压报红色 |

**环境**:工作台+防静电垫(PolyHaven `rubber_tiles` 纹理)、四旋翼机身与桨叶脚架(程序化)、`metal_toolbox`/`screwdrivers_02`/`pliers`/`bench_vice_01`/`magnifying_glass_01`/`circuit_board`、`retro_multimeter`(作远端电压表外观基准)。`render_hints`:ortho_scale≈1.1,grid_extent≈1.8,cue_scale=0.8,label_offset=0.10。

---
