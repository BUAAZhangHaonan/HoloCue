> 本设计分册提取自 `docs/09_新场景与任务设计.md`（扩展轮，评审修订版）；四判据、与初版关系、验收要点以该总纲为准。

## 场景四 `server_rack` 数据机柜排障

**世界**:模块化数据中心机柜排障。运维工程师站在机柜前门侧:前面板插满 1U/2U 节点与交换机,柜顶告警灯,最深处节点背面被多层机架结构遮挡。

**视点与深度(调焦距离为沿视轴近似值)**:`camera_position_m=[1.12,-1.02,1.30]`,`camera_look_at_m=[-0.3548,0.0219,1.0289]`(as-built,含小车与柜顶全画幅)。本文各场景的 ortho_scale、锚点数值为设计初值;建模定稿后以 `scenes/<id>/scene.json` 与 `runs/scene_v2/build_<id>.log` 的实测为准。
| 层 | 对象 | 位置(y,z) | 沿视轴距离 | task_role / depth_requirement | N/σ 倾向 |
|---|---|---|---|---|---|
| 近 | SPARE→SLOT4 插入 | y≈-0.25, z≈1.02 | ≈1.6m | current / precise | 高 N,小 σ |
| 中 | NODE3 背面(机柜深处) | y≈+0.33, z≈0.55(下移深仓位) | ≈2.3m | next / persistent | 中 N,大 σ |
| 远 | ALARM 柜顶告警灯 | y≈+0.35, z≈1.62 | ≈2.6m | background / persistent | 低 N,大 σ |

**任务脚本**:
- 初始指令:`先把备用节点 SPARE 插进 4 号槽位 SLOT4,然后检查 3 号节点 NODE3 背面的光纤接口,柜顶告警灯 ALARM 全程保持监控。`
- 打断:`先停下,看看 NODE3 背面,SPARE 的插入任务保留。` → interrupt,NODE3 变 current,原队列挂起;`恢复刚才 SPARE 的插入任务。` → resume。
- 扩展测试输入:

| 输入 | 检查点 |
|---|---|
| 把 FAN 拧一下 | FAN 有 rotate 但缺角度 → clarify,不编造 0 度 |
| 把 NODE3 拧一下 | NODE3 无 rotate 能力 → 校验层拒绝(对应初版"C 转 30 度"用例) |
| 把 SPARE 再往里插一点 | 锚点动作终点唯一 → interrupt 按既有 SLOT4 锚点演示,不 clarify 不改终点 |
| 先拔 FAN 看滤网背面 | FAN 无 inspect_back → 校验拒绝 |
| 告警灯红了你先停一下 | 语义上暂停;事件来源为确定性脚本时间线,非感知网络 |
| 连续快速发两条指令 | 只有最新 epoch 可提交 |

**为什么强契合**:近端对准 4 号槽位精插与远端柜顶告警监控发生在同一任务里、不同调焦面(1.6m vs 2.6m);平面基线(角落 HUD 常亮指示)不提供调焦轴,告警与操作共享屏幕注意资源——全息分层的收益假设在此最典型,由对照实验测定。NODE3 背面在机柜内部,被前部节点与理线架多层遮挡,转台式 ghost 副本是自然的查看方式。指令含槽位编号指代、部件级描述("背面的光纤接口")、"全程保持监控"持续性要求,需要 LLM 区分 current/next/background 三角色。任务图差异化标记:本场景是"单 precise 精插 + 深处查背面 + 远层监控"结构。

**交互对象(锚点为参照对象局部坐标)**:
| id | label | capabilities | anchors | description |
|---|---|---|---|---|
| SPARE | 备用节点 | point, insert | — | 1U 备用计算节点,沿导轨水平插入 |
| SLOT4 | 4 号槽位 | point | insertion=[0,0,0](pose 世界位 [0,0.28,1.02],槽体中心即终点,SPARE 满插就位) | 空槽位,带导轨与定位柱 |
| NODE3 | 3 号节点 | point, inspect_back | — | 背面有四个光纤接口和提把手 |
| ALARM | 柜顶告警灯 | point, wait | — | 红色为故障,绿色为正常 |
| FAN | 风扇模块 | point, rotate | — | 滤网需旋转取出,顶部刻线对齐 |

**环境**:机柜框架(立柱+前后门框)、已装节点面板×6(散热孔与小 LED 点缀)、理线架与线缆束、防静电架空地板、机房墙。素材策略:PolyHaven `worn_metal_rack`(915×600×1900mm,作机柜骨架)+ `modular_electric_cables`(线缆束)+ `circuit_board` + `security_camera_01`;PBR 纹理 `metal_plate_02`/`factory_wall`/`hangar_concrete_floor`;1U 面板程序化建模。`render_hints`:ortho_scale≈2.2,grid_extent≈2.5,cue_scale=1.0,label_offset=0.12。

---
