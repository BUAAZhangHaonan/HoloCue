# 场景任务提案 Agent 系统(ZCode 主进程 + 三独立 SubAgent)

本目录是一个由 **ZCode Agent 驱动**的提案—审查工作区,不是可执行脚本,也不依赖本地 4B 模型或外部 API。主进程(ZCode 主会话)负责提案与修订;三个**相互独立的 SubAgent 会话**分别按各自章程审查;三轮独立检验全部通过,提案才归档为备选。

若环境中无法调用 SubAgent,按 AGENTS.md 记录阻塞于 `reviews/BLOCKED.md`,不得由主进程写自评冒充独立验证。

## 流程协议

1. **提案**:主进程依据 `requirements.md` 撰写提案,存 `proposals/<scene_id>_v1.md`(结构见 `proposal_template.md`)。提案先于一切审查完成。
2. **三轮独立审查**:三个独立 SubAgent 会话(章程见 `reviewers.md`),每次都是全新会话、互不知晓彼此结论,只读 `requirements.md` + 提案文件:
   - `research` — 研究契合度(docs/09 四判据 + 研究定义边界)
   - `realism` — 真实与实用(常见职业场景,拒绝猎奇/摆拍)
   - `feasibility` — 工程可行与差异化(合法枚举、锚点、资产量级、与现有 9 场景任务图不重合)
   报告写入 `reviews/<scene_id>/round<N>_<role>.md`,结论行 `VERDICT: pass|fail`。
3. **判定与迭代**:
   - 三份报告全部 pass → 提案复制登记到 `candidates/`,记入 `candidates/INDEX.md`。
   - 任一 fail → 主进程修订出 `vN+1`(旧版保留),**三轮审查全部重跑**(round N+1),因为修订改的是整份提案。
   - 修订不设轮数上限,但每轮全量留痕;连续 fail 说明方向不对,应放弃该 scene_id 并留档。
4. **边界**:通过备选 ≠ 建模定稿。备选场景进入建模后仍沿用 `docs/09` §验收要点(含 Blender 渲染后的三轮独立视觉审核),那是另一道门。

## 文件一览

| 路径 | 用途 |
|---|---|
| `requirements.md` | 审查依据(三轮共用,含现有场景任务图基准) |
| `reviewers.md` | 三个审查章程与报告格式 |
| `proposal_template.md` | 提案结构模板(对齐 docs/09 场景设计) |
| `proposals/` | 主进程提案,按 `<scene_id>_v<N>.md` 版本化 |
| `reviews/<scene_id>/` | 各轮审查报告(roundN_research/realism/feasibility) |
| `candidates/` | 三轮全通过后的备选归档 + INDEX |

## 运行记录

- 2026-09-17:系统建立。首批三份提案 `infusion_ward` / `cnc_toolchange` / `dive_fillstation` 进入 round1 审查;背景:用户判定 `dig_site`(考古探方)过于猎奇,新提案路线改为"真实常见职业场景 + 内禀深度冲突"。
- 2026-09-17 round1 结果:
  - `infusion_ward` v1:research **pass**;realism **fail**(标签核对排在开放三通之后,违反"先核对后给药"查对时序);feasibility **fail**(任务图与 drone_bench 重合;相机/深度数值实算矛盾)→ 修订 v2,三轮全部重跑(round2)。
  - `cnc_toolchange` v1:realism **fail**(手动盘车+隔套目视查拉钉不符行业习惯);feasibility **fail**(12 工位盘 60° 到不了 3 号位,算术不成立;深度表与相机矛盾;research 因账号速率限制未跑成,由 v2 的 round2 取代)→ 重构任务链为"模式旋钮切档→插刀→拔刀点检",修订 v2,三轮全部重跑(round2)。
  - `dive_fillstation` v1:research **pass**;feasibility **pass**(5 条次要问题留档,最主要者为近层沿视轴距离与相机几何的量级偏差,属设计初值层面);realism 派发时遇账号速率限制未跑成,非内容原因,补派(仍属 round1/v1)。
  - 备注:一次性并发 9 个 SubAgent 触发账号速率限制,后续按每批 ≤4 个派发;速率限制属基础设施阻塞,不伪造审查结论。
- 2026-09-17 round2–round4(最终结果,三份提案全部通过三轮独立检验并归档 `candidates/`):
  - `infusion_ward` **v2 于 round2 三轮全过归档**。
  - `dive_fillstation` v1 realism 补审 **fail**(检验钢印真实规程在瓶肩、充装前核对,v1 虚构到汇流排接头背面)→ v2 修正(瓶肩钢印、开阀前时序、软管接头插入、几何重算)→ **round2 三轮全过归档**。
  - `cnc_toolchange` v2 三轮中 research/feasibility **fail**(拉钉端面为轴向端面,非径向面)→ v3 修局部坐标系声明(刀柄水平、局部 Z 竖直)→ round3 realism **fail**(POCKET3 距开口 180°,无转位步骤则拔刀不可达)→ v4 将 T03 移至刀具车(上刀前点检备用刀)→ **round4 三轮全过归档**。
  - 迭代统计:3 提案 × 3 章程 = 21 次独立 SubAgent 审查会话(含 2 次速率限制未跑成);每轮修订后三轮全部重跑,全部历史版本与报告留痕。


