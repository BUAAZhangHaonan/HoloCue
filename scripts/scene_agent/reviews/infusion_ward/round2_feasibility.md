# infusion_ward 第 2 轮 feasibility 审查报告

- 审查人:独立 SubAgent(章程:feasibility)
- 提案版本:v2
- 结论:pass

## 逐条检查

| # | 检查项 | 结论 | 证据(提案原文摘录 + 分析) |
|---|---|---|---|
| 1 | 交互对象 5–8 个、ID 合法、capabilities 属于合法枚举、能力负例 ≥2 条 | 通过 | 交互对象表共 6 个:「PUMPCASSETTE \| 一次性泵盒 \| point, insert」「SLOT2 \| 2 号泵槽 \| point」「STOPCOCK \| 三通旋塞 \| point, rotate」「BAG1 \| 5% 糖袋 \| point, inspect_back」「BAG2 \| 10% 糖袋 \| point」「MONITOR \| 床头监护仪 \| point, wait」。数量 6 ∈ [5,8],含消歧项 BAG2;ID 全 ASCII;capabilities 均属 {point, rotate, inspect_back, insert, assemble, wait} 合法枚举。task_role 用到 current/next/background,深度表「current / precise」「next / **neutral**」「next / persistent」「background / persistent」均为合法值。能力负例恰 2 条:「把 MONITOR 转过来 \| MONITOR 无 rotate → 校验拒绝」「把糖袋转 30 度 \| BAG1 无 rotate → 校验拒绝」,均为要求无该能力的对象执行该动作并触发校验拒绝,满足 ≥2(两条同为 rotate 类见次要建议 4)。 |
| 2 | 锚点可写成参照物局部坐标;相机与调焦距离数值量级合理;坐标系约定未被违反 | 通过(独立复算自洽) | 原文:「`camera_position_m=[0.40,-1.05,1.45]`,`camera_look_at_m=[-0.15,0.55,1.35]`(设计初值)。沿视轴距离按 \|(P−C)·d̂\| 计算」;「SLOT2 … insertion=[0,0,0](设计初值;世界位约 [0.05,0.15,1.18],槽体中心即满插终点)」;「沿视轴调焦距离 1.26 / 1.64 / 2.50m,相邻层差 0.38 / 0.86m(≥0.3m)」;「『顺时针 90 度』显式角度(fixture 记 -90)」。**独立复算**:d=L−C=(−0.55,1.60,−0.10),\|d\|≈1.6948,d̂≈(−0.3245,0.9440,−0.0590)。SLOT2 [0.05,0.15,1.18]→\|(P−C)·d̂\|=1.262m;STOPCOCK [0.10,0.20,0.95]→1.307m;BAG1 [−0.05,0.55,1.80]→1.636m;MONITOR [−0.35,1.35,1.60]→2.500m。四个数值与提案逐一吻合,层间差 0.37/0.86m≥0.3m,与提案声明一致——v2 的几何自洽性由本次独立计算确认,非采信提案自述。锚点写在参照物 SLOT2 局部坐标系且「槽体中心即满插终点」终点唯一,「把泵盒再插深一点 \| 锚点终点唯一 → interrupt 按既有 SLOT2 锚点演示,不改终点」符合锚点约定。坐标为米制 Z-up(对象高度 z∈[0.95,1.80],病房挂袋/泵/监护仪高度合理);相机高 1.45m 为站立眼高,量级合理;四对象相对视轴偏角约 7°–19°,同视场可见;顺时针记 −90 符合约定。STOPCOCK(1.31m)与 SLOT2(1.26m)仅差 0.05m,提案已诚实标注「近(步骤,非独立层)」,不计入分层,无虚报。 |
| 3 | 资产可程序化建模 + CC0 完成、工作量同量级;环境/交互划分清晰 | 通过 | 原文:「病床与床头柜、输液架底座与挂钩、治疗车、病房墙地(常规 PBR)、隔帘、呼叫按钮(程序化建模为主;管路与袋体半透明材质程序化生成)」。全部为常规病房物件,无稀有或高成本资产,半透明袋/管为程序化材质,路线可行;工作量与 server_rack、drone_bench 等现有 v2 场景同量级。环境节所列对象仅渲染、不进 LLM 清单,与 6 个交互对象的表格划分清晰(泵体以 SLOT2 为交互代理、泵壳/架体归环境,边界明确)。 |
| 4 | 差异化标记与 §5 表全部 9 个场景任务图结构不重合 | 通过(存在元素级重叠,见次要建议 1–3) | 原文标记:「**差异化标记**:**depth_requirement 全三档同场主链**(precise 插入 / persistent 核对与监护 / neutral 在链三通旋转)+ **设备报警事件驱动的『background 提升 current → resume 恢复』闭环**」;打断语义:「先停下,监护仪血氧报警了,先看 MONITOR,泵的事保留。」→「MONITOR 由 background 提升为 current(wait),装管队列挂起」「报警处理完了,继续开三通。」→ resume;「(监护仪报警为确定性脚本时间线事件——状态在约定时刻翻转,非感知网络、非 LLM 输出。)」(报警机制为确定性脚本状态 + 用户话语驱动的重规划,不引入感知网络或 LLM 自由输出,工程上可确定性实现,且与「epoch 竞争仅最新可提交」的现行约束一致)。**逐个对比 §5 基准表(9 场景,本审查独立完成)**:① blocks/connector/control_panel(v1 桌面教具、接口闭环验证)——无病房尺度分层、无 background 监控与打断恢复,不重合;② server_rack(单 precise 精插 + 深处查背面 + 远层告警监控)——**最接近**:本场景脊柱(单 precise 插入 + BAG1 查背面 + MONITOR 远层报警监控)与其三项同型,但基准表标记不含 neutral 主链节点,亦无 background→current 提升与 resume 恢复边,且本场景主链多一个 neutral rotate 节点并覆盖全三档,整体任务图不重合;③ drone_bench(双 precise 连续步 + 遮挡查背面 + 远层读数监控)——本场景「主链仅一条 precise(泵盒插入),三通旋转为 neutral 档」,precise 结构不同,不重合;④ shelf_picking(双 background 监控 + 同深度不同角色对照)——静态双背景、同深度对照,与单背景事件提升 + 跨层主链不同,不重合;⑤ optical_bench(跨层内禀注意(手近眼远)+ 参数化角度更新)——共享「手近眼远」注意元素,但其标记为参数化角度更新,本场景为固定 90° 旋转 + 事件打断恢复,不重合;⑥ dig_site(非插入类 current + neutral 档,已判猎奇待替换)——非插入主链与本场景插入主链不同,不重合;⑦ engine_bay(rotate + insert + inspect_back 复刻验收)——与本场景主链能力三元组完全相同(见次要建议 2),但基准表标记不含 background 监控节点、三档分层与打断恢复边,不重合。两个标记组件(全三档同场主链、事件驱动提升+恢复闭环)在 9 个基准标记中均未出现。结论:结构不重合成立。 |
| 5 | 提案结构完整(模板各节齐全,无缺项) | 通过 | 各节齐全:「## 世界」「## 视点与深度」(含深度表与 N/σ 倾向列,N←角色、σ←档位,保持确定性映射、未变成 LLM 自由输出)「## 任务脚本」(初始指令/打断-恢复/8 条扩展输入)「## 交互对象(锚点为参照对象局部坐标)」(id/label/capabilities/anchors/description 五列齐全)「## 环境」「## 为什么强契合」(四判据逐条映射,全息收益措辞为「仿真演示假设」)「## 修订记录(v1 → v2)」。无缺项。 |

## 主要问题(fail 必填,pass 留空)

(无)

## 次要建议

1. **server_rack 脊柱重叠是最近点**:「单 precise 精插 + 查背面 + 远层告警监控」三项与本场景同型,差异化全靠 neutral 主链节点与「提升-恢复」两条边支撑。建议在后续 JSON/演示验收中把「MONITOR background→current(wait)→resume 闭环」与「三通 neutral 在主链」列为必验项,防止实现退化成 server_rack 的复刻。
2. **提案自称「逐个」对比但实际只覆盖 drone_bench/server_rack/dig_site 三个**,未显式对比 v1 教具、shelf_picking、optical_bench、engine_bay;其中 engine_bay 标记「rotate + insert + inspect_back」与本场景主链能力三元组完全相同,是仅次于 server_rack 的重叠点。本报告已代为补全 9 场景对比并确认不重合,建议 v3 把遗漏的对比写进提案。
3. **两处无法从 §5 基准表独立验证的内部语义断言**:「server_rack 的告警仅为『暂停』语义、其打断由用户自主选择对象」,以及 engine_bay 主链是否实际覆盖三档(基准表未标档位)。本审查按基准表判定不重合;若后续核对发现 server_rack 已含提升/恢复语义、或 engine_bay 主链同为全三档,对应标记组件的独立性将部分失效,需以实据复核。
4. 两条能力负例均为 rotate 类,建议补充一条非 rotate 负例(如要求 BAG2 执行 insert 或 inspect_back)以覆盖不同校验路径。
5. SLOT2 精插焦点沿视轴 1.26m(欧氏约 1.28m)对「手前近端操作」略偏远,属设计初值范畴(§4 明示只查量级);建模定稿时建议复核护士站位与治疗车取盒起点,并按 `configs/scenes/<id>.json` 实测更新深度表。
