# 场景模板使用说明

本目录提供当前 1.1 场景契约的编写示例。下划线开头目录不进入运行场景清单。模板资产尚未生成，也没有验收记录。

1. 在获准新增场景时复制为 `scenes/<id>/`，修改 `scene_id`、所有资产路径、标题、对象说明和任务。模板中的 example 必须替换为实际目录名。
2. 使用统一 `modeling.py` 中已有 recipe；新增几何职责也在统一建模模块实现。填写实际尺寸、位姿、动作轴、源目标接合坐标系、路径间隙和检查面。环境建模同样需要核对场景支持，不可只改标识后认定可运行。
3. 模型请求使用对象说明和 `initial_instruction`。验收端使用 `task_contract.ordered_steps`、常驻目标和临时检查输入，保留同一对象的重复动作。
4. 通过 `scripts/scenes/build_simulation_assets.py --scenes <id>` 构建资产，核对网格、比例、接合开口、材质与标签。执行前设置项目内部临时目录与缓存，并采用资源守卫。
5. 使用 `scripts/scenes/build_all.sh` 构建原生 Blender 场景。当前入口枚举全部配置，输出每个场景目录的 `scene.blend`。
6. 运行场景检查、全部有效测试、几何与渲染检查。真实模型验收使用 `scripts/tests/live_twelve_scenes.py` 所实现的完整任务检查；新增场景须同时满足实际脚本与验收范围。
7. 在真实 Viser 与 Blender 中保存工作区域、特写、检查面和运动证据，验证暂停、临时检查、完成、恢复与实体位姿。宽屏和较窄窗口分别检查。
8. 记录资产来源和许可、实际运行命令、依赖版本、代码与证据摘要。独立审查仅记录实际执行结果，缺项保留为待执行。

详细要求见 [系统架构](../../docs/SIMULATION_ARCHITECTURE.md)、[场景约定](../../docs/SCENE_REVIEW.md) 和 [验证标准](../../docs/VALIDATION.md)。
