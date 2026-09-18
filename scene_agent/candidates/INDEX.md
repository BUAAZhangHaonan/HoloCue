# 备选场景索引(candidates)

通过后的设计正本与评审报告随场景套件归档（`scenes/<scene_id>/docs/design.md`、`scenes/<scene_id>/reviews/`）；本目录只保留索引。

通过「三轮独立 SubAgent 检验全部通过」的场景提案。通过 ≠ 建模定稿:进入建模后仍走 docs/09 §验收要点(含渲染三轮视觉审核)。

| scene_id | 标题 | 通过版本 | 轮次 | 三轮报告 | 差异化标记 |
|---|---|---|---|---|---|
| infusion_ward | 病房输液泵装管与床头监护 | v2 | round2(v1 于 round1 被 realism/feasibility 拦下,修订后全过) | `../../scenes/infusion_ward/reviews/round2_{research,realism,feasibility}.md` | depth_requirement 全三档同场主链 + 设备报警事件驱动的「background 提升 current → resume 恢复」闭环 |
| dive_fillstation | 潜水气瓶充装前核验与接通 | v2 | round2(v1 被 realism 拦下:钢印位置虚构;v2 改瓶肩核对、开阀前时序,全过) | `../../scenes/dive_fillstation/reviews/round2_{research,realism,feasibility}.md` | 安全规程内禀的全程持续盯压(定量红线表) + inspect_back 对象与消歧组同体(瓶肩钢印) |
| cnc_toolchange | 立式加工中心手动装刀与拉钉点检 | v4 | round4(v1 盘车算术+习惯问题;v2 径向面几何错误;v3 拔刀可达性;v4 全过) | `../../scenes/cnc_toolchange/reviews/round4_{research,realism,feasibility}.md` | 链首远层 precise rotate(模式切换使能手动作业) + 远端同距双角色(current 旋钮与 background 面板同在最远层) |

## 归档记录

- 2026-09-17:`infusion_ward` v2 通过三轮独立审查(research/realism/feasibility 均 pass),归档。v1 的用药查对时序问题、任务图与 drone_bench 重合问题、几何矛盾问题在 v2 修复;round1/round2 全部报告留痕于 `../../scenes/infusion_ward/reviews/`。
- 2026-09-17:`dive_fillstation` v2 通过三轮独立审查,归档。v1 的钢印位置虚构问题(检验标记实际在瓶肩、须充装前核对)在 v2 修复,同时修正插入动作(软管快插接头接瓶阀出口)与几何自洽;全部轮次报告留痕于 `../../scenes/dive_fillstation/reviews/`。
- 2026-09-17:`cnc_toolchange` v4 通过三轮独立审查,归档。历轮修复:v1→v2 删手动盘车(行业习惯+12 工位 60° 算术矛盾);v2→v3 修拉钉端面径向面几何(局部 Z 竖直、转台式);v3→v4 把 T03 移到刀具车(180° 拔刀不可达);全部轮次报告留痕于 `../../scenes/cnc_toolchange/reviews/`。

