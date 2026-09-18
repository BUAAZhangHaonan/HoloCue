# 提案 `<scene_id>`:<标题>(vN)

一句话概述。**差异化标记**:<与现有 9 场景任务图的结构差异,一句话>。

## 世界

场景世界观、站位与纵深布局(谁、站在哪、近中远各有什么、为什么这条纵深是任务内禀的)。

## 视点与深度

`camera_position_m=[x,y,z]`,`camera_look_at_m=[x,y,z]`(设计初值,建模定稿后以 `scenes/<id>/scene.json` 实测为准)。

| 层 | 对象 | 位置概要 | 沿视轴距离 | task_role / depth_requirement | N/σ 倾向 |
|---|---|---|---|---|---|

(N/σ 倾向列只表述两条独立规则的方向:N 随 priority 升高;σ 档位随 depth_requirement 取 precise 小 / persistent 大 / neutral 中,不存在直接耦合。)

## 任务脚本

- 初始指令:`...`
- 打断:`...` → interrupt 语义说明
- 扩展测试输入表:

| 输入 | 检查点 |
|---|---|

(必须覆盖:消歧 clarify、缺角度 clarify、锚点类不编造、能力负例 ≥2、事件驱动 interrupt/pause、epoch 竞争。)

## 交互对象(锚点为参照对象局部坐标)

| id | label | capabilities | anchors | description |
|---|---|---|---|---|

## 环境

环境对象与素材路线(程序化 / PolyHaven / ambientCG,CC0)。

## 为什么强契合

逐条对四判据给论证:
1. 焦深分层必要性:...
2. 遮挡与背面信息:...
3. LLM 解析必要性:...
4. 空间锚定动作:...
