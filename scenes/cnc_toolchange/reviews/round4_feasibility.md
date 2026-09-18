# cnc_toolchange 第 4 轮 feasibility 审查报告

- 审查人:独立 SubAgent(章程:feasibility)
- 提案版本:v4
- 结论:pass

## 逐条检查

| # | 检查项 | 结论 | 证据(提案原文摘录 + 分析) |
|---|---|---|---|
| 1 | 交互对象 5–8 个、ID 合法、capabilities 合法枚举、能力负例 ≥2 条 | 通过 | 交互对象表共 6 个 id:MODESWITCH(point, rotate)、T09(point, insert)、POCKET9(point)、T03(point, inspect_back)、MAG(point)、PANEL(point, wait)。6 ∈ [5,8];id 全部为 ASCII 大写字母+数字;所用能力 point/rotate/insert/inspect_back/wait 全部属于合法枚举,未发明新能力。能力负例恰有 2 条:「把刀库盘 MAG 转一下——MAG 仅 point(电控转位,不手动盘车)→ 校验拒绝」「把面板转过来——PANEL 无 rotate → 校验拒绝」,均为「无该能力的对象被要求执行该动作→校验拒绝」型,满足 ≥2。task_role 仅用 current/next/background,depth_requirement 仅用 precise/persistent,均为合法枚举值。 |
| 2 | 锚点写参照物局部坐标;相机与调焦距离量级合理;坐标系约定未被违反 | 通过 | 锚点原文:「POCKET9 … insertion=[0,0,0](设计初值;世界位约 [0.72,0.08,1.12],套孔中轴即满插终点)」——写在参照对象 POCKET9 自身局部坐标系,合法可写。相机原文:「`camera_position_m=[1.05,-0.95,1.45]`,`camera_look_at_m=[0.00,0.45,1.15]`(设计初值)」。**独立复算** |(P−C)·d̂|:d=[−1.05,1.40,−0.30],\|d\|≈1.7755,d̂≈[−0.5914,0.7885,−0.1690]。MODESWITCH [0.10,1.00,1.45]:(−0.95,1.95,0)·d̂≈**2.099m**(提案 ≈2.10 ✓);T09/POCKET9 [0.72,0.08,1.12]:(−0.33,1.03,−0.33)·d̂≈**1.063m**(提案 ≈1.06 ✓);T03 [0.35,0.38,1.20]:(−0.70,1.33,−0.25)·d̂≈**1.505m**(提案 ≈1.51 ✓);PANEL [0.10,1.02,1.45]:(−0.95,1.97,0)·d̂≈**2.115m**(提案记 ≈2.10,偏差约 1.6cm,量级与结构结论不受影响,列入次要建议)。层间差实算 0.44m / 0.61m(提案 0.45/0.59,舍入差),均 ≥0.3m;MODESWITCH 与 PANEL 层内差仅 1.6cm,「同处最远层」数值成立。坐标系约定:高度 1.12–1.45m、距离 1–2m 量级符合米制 Z-up 车间站位;旋转原文「『顺时针 90 度』显式角度(fixture 记 -90)」与章程「顺时针输入在 fixture 中记负角」一致。 |
| 3 | 资产程序化建模 + CC0 可完成、工作量与 v2 同量级;环境/交互划分清晰 | 通过 | 环境节原文:「机床钣金机身与安全门、主轴头、工作台与夹具、排屑槽、车间地面与墙、中段刀具车(程序化建模为主;刀柄为圆柱+锥面标准件,刀套沿圆盘阵列)」。交互件均为低多边形基础体(三档旋钮、BT40 圆柱+锥面刀柄、刀套、圆盘、面板屏),环境件为程序化钣金/台面;最重资产是机床机身,但已声明程序化路线,与 server_rack 机柜、drone_bench 检修台同一量级。环境清单与交互表无 id 交叠;刀具车为环境(仅渲染),其上的 T03 为交互对象,划分清晰,环境对象未进 LLM 清单。 |
| 4 | 差异化标记与 §5 全部 9 场景任务图结构不重合(逐个对比) | 通过 | 提案标记原文:「**链首远层 precise rotate**(模式切换是手动装刀的安全前置,旋转使能的是作业模式而非对象位置)+ **远端同距双角色**(current 操作对象 MODESWITCH 与 background 监控对象 PANEL 同在最远层)」。逐个对比(本审查自行完成,不止依赖提案自述):① blocks/connector/control_panel(v1,接口闭环验证)——为 API 闭环验证图,无「远层精确操作→近端锚插→中段查背面」链,不重合;② server_rack(单 precise 精插+深处查背面+远层告警监控)——共享「精插+查背面+远层告警监控」要素,是最近邻居之一,但其唯一 precise 在近端、无链首远层 rotate、监控对象与操作对象不同层,本场景双 precise 分处 2.10m/1.06m 且 current/background 同层(层内差 1.6cm),结构不重合;③ drone_bench(双 precise 近端连续两步+遮挡查背面+远层读数监控)——提案自述对比成立:本场景双 precise 远/近分离且中间隔查背面,另有同层双角色,不重合;④ shelf_picking(双 background 监控+current/next 同中层对照)——同深度对照的角色组合与层位不同(current/background 且同最远层 vs current/next 同中层),不重合;⑤ optical_bench(近端参数化迭代角度更新)——本场景 rotate 为一次性模式切换、位于远端、无参数化迭代,不重合;⑥ dig_site(非插入 current+neutral,已判猎奇待替换)——本场景有锚定 insert、无 neutral 档,不重合;⑦ engine_bay(rotate+insert+inspect_back 复刻验收)——能力三元组与本案相同,是另一最近邻居,但其为近端复刻验收图:无链首远层 precise rotate、无同层 current/background 双角色、无远端告警监控,层位分布与角色结构不同,不重合。提案断言「现有 9 场景的 rotate 全部位于近/中端」与 §5 标记表无矛盾(表中无任何远层 rotate 标记)。结论:差异化标记在结构上对 9 场景全部成立;与 server_rack、engine_bay 的相似度应显式声明(见次要建议)。 |
| 5 | 提案结构完整(模板各节齐全,无缺项) | 通过 | 各节齐全:差异化标记与逐场景对比、修订记录(v1→v4 四轮)、世界、视点与深度(相机显式+四行深度表含世界位/沿视轴距离/role/depth_requirement/N-σ 倾向)、任务脚本(初始指令+打断/恢复+7 条扩展测试输入表)、交互对象表(id/label/capabilities/anchors/description 五列俱全)、环境、为什么强契合(四判据逐条)。v4 修订内容与正文自洽:T03 已改为「刀具车上平放」、POCKET3 已删除、脚本无拔刀步骤、MAG 保持 point-only,修订记录与正文一致,无缺项。 |

## 主要问题(fail 必填,pass 留空)

(无)

## 次要建议

1. PANEL 沿视轴距离实算为 ≈2.115m,提案记 ≈2.10m;「同距双角色」实际层内差约 1.6cm。建议深度表写为 ≈2.10–2.12m 或注明与 MODESWITCH 的层内差,避免后续轮次被误判为深度表与坐标不自洽。
2. 提案自述的结构对比仅覆盖 drone_bench、optical_bench、shelf_picking 三个;建议补 server_rack 与 engine_bay 各一句(server_rack 共享「精插+查背面+远层告警监控」要素、engine_bay 共享 rotate+insert+inspect_back 能力集),差异化结论不变,但可预先封堵最近邻居的争议。
3. 「现有 9 场景的 rotate 全部位于近/中端」未给逐场景出处;§5 标记表虽无矛盾,建议补一句出处说明,以免该断言被质疑为无据。
