# 给开发者 Agent 与仿真环境调研

HoloCue 第一版实现说明  ·  2026 年 9 月 15 日

> 目标是尽快得到真实模型驱动、可暂停恢复、可观察和可复现的交互原型。优先把任务状态和两个可视化环境接稳，再接入合作方的光学后端。

![图 1  开发侧负责语义、状态和显示包，光学端通过独立适配器接入。](figures/03_architecture.png)

## 选定的轻量架构

Qwen3.5 通过兼容 OpenAI 的 HTTP 接口输出严格 JSON。LangGraph 仅含解释与场景校验两个节点。SQLite 保存权威任务状态，FastAPI 暴露会话与显示包，Viser 提供主要交互界面，Blender 共用场景和任务版本。

这个组织便于调试语言理解、状态迁移和显示动作。提示词存放在 prompts/planner.md，几何与任务清单独立存放。软件已经给出基础实现，现场执行重点是依赖适配、真实模型和视觉联调。

第一阶段输入是已知场景与任务历史。API 保留图像输入位置，后续可以加入画面识别；当前结果按实际使用的信息条件记录。

# 01  Agent 框架与状态选择

| 框架或参考 | 有用的能力 | 本项目的取舍 |
|---|---|---|
| LangGraph [R11][R12] | 显式流程、状态和中断机制。 | 选为两个节点的规划流程；应用 SQLite 负责唯一权威任务状态。 |
| smolagents [R13] | 轻量工具调用与交互修改计划示例。 | 适合读实现思路，当前项目保持既定 LangGraph，避免双框架维护。 |
| Guided Reality [R06] | 任务步骤和多种空间提示。 | 借鉴提示类型与步骤组织，显示物理由光学模块定义。 |

LangGraph 的 interrupt 在指定节点处暂停，恢复时节点可能重新运行。因此应用层要明确区分等待用户信息、取消旧请求和暂停显示动作。[R11]

## 任务打断如何实现

每次用户请求携带 expected_revision 和 request_id。服务先增加 epoch 并冻结旧动作，然后提交模型推理。返回结果必须仍属于当前 epoch，才能通过事务更新任务。旧请求即使稍后返回，也不能覆盖新计划。

interrupt 把完整队列压入挂起栈，包括角度、对象和 task_id。resume 从栈中恢复原任务。临时任务由用户明确确认完成，动画结束不触发任务完成。未知对象、能力缺失或格式错误可见报错，原始模型输出保留。

LLM 的实验价值放在开放语言、约束组合与临时改计划。程序中的状态机负责执行正确性，两者分别评价。

# 02  Blender 与 Viser 的分工

| 工具 | 在原型中的作用 | 可直接使用的资源 |
|---|---|---|
| Viser [R14][R18] | 网页场景、自然语言输入、暂停与恢复、参数面板、动态提示。 | viewer.py，九组 GLB，三个 scene JSON。 |
| Blender | 资产检查、可复现渲染、同会话动作预览。 | build_blender_scene.py，blender_live_bridge.py。 |
| Blender MCP [R15] | 辅助尝试资产与布局。 | 作为参考；正式闭环使用固定受控接口。 |
| BlenderProc [R16] | 后续批量数据、深度和标注生成。 | 阶段一复用手工定义的清单，后续可对接。 |

Blender 的 bpy 操作在主线程执行。桥接脚本用工作线程拉取 HTTP 状态，再由定时器应用到场景。Viser 与 Blender 使用同一份 DisplayPacket，避免两套独立任务逻辑。

用户看到的半透明模块或插头是显示副本，动作不修改真实场景对象。当前 σ 面板是显式标注的概念预览；真实焦点扫描数据接入后，可在同一位置展示测量结果。

## 三个场景需要看清楚

旋钮场景检查环形箭头方向、30 度参数和 C 背面演示。插接场景检查插头朝向与插入锚点。积木场景检查对象指代、运动终点和后续步骤。所有资产用米和 Z 向上，GLB 保留颜色，OBJ 便于兼容导入。

包内已经包含可导入模型。实际 .blend 文件由 4029 的已有 Blender 构建，现场截图应来自该构建结果。

# 03  本地模型与资源约束

官方提供 Qwen3.5-4B 和 9B 的多模态 checkpoint，并给出 vLLM、SGLang 部署方法。第一版先用 4B 验证结构化计划；9B 在独立配置下评估复杂指令。API 使用 enable_thinking=false，模型输出经 JSON Schema 与场景约束双重检查。[R08–R10]

| 配置项 | 第一阶段设置 |
|---|---|
| 项目 | 4029 的 /home/hdd3/zhanghaonan/projects/holocue |
| 模型来源 | 先查既有 checkpoint；4028 Models 只读复制；需要时下载官方权重。 |
| 计算设备 | 仅物理 GPU 1、2；默认 4B 使用一张获准空闲卡。 |
| 推理 | 8192 上下文、1 并发、1600 输出上限、显存比例默认 0.70。 |
| 环境 | 应用 .venv 与模型 .venv-model 分开；复用既有 Blender。 |

服务器型号、显存和管理员红线尚待现场盘点。默认保留至少 32 GiB 或总内存 20%，模型进程树 RSS 上限 32 GiB；真实规范更严格时按真实规范执行。资源守卫以 GPU UUID 建立掩码，拒绝其他物理卡。

部署脚本是经过静态检查的启动基础。执行前核对已装引擎的版本与 --help；对不兼容参数进行有记录的适配，固定可运行版本。官方大上下文示例与本项目的短任务设置分别理解。

模型文件检查包含配置、分片头和实际长度；Hub 哈希验证或源文件哈希另行记录。模型加载成功、文件校验成功和方法性能是不同验收项。

# 04  现场验收与后续接口

| 验收层 | 应保存的证据 |
|---|---|
| 软件核心 | 测试结果、状态快照、请求幂等与过期响应检查。 |
| 真实模型 | live 模式、原始请求与响应、三场景结果、中断恢复测试。 |
| 视觉联动 | 实际 Viser 截图、Blender 渲染、同会话联动、中断前后视频。 |
| 资源与复现 | GPU UUID、显存和主机峰值、引擎版本、模型来源、重启命令。 |
| 独立复核 | 三个真实 SubAgent 会话的报告与证据哈希，覆盖安全、视觉、架构。 |

交付环境已运行核心测试，36 项通过，1 项 LangGraph 集成因缺少依赖跳过。Blender、Viser 和本地 Qwen 的现场联调交给执行工具完成。replay 是独立软件测试入口，最终验收必须使用真实 live 模型。

## 给光学侧预留的接口

DisplayPacket 统一对象、动作、N、σ、单位、坐标、任务版本和标定版本。以后只需增加一个实现 capabilities、submit、cancel 的适配器，将其送往内网光学服务。API 默认环回，远程演示用 SSH，内网开放需要认证配置。

第一阶段保持单操作会话、显式完成、最多八条提示。后续加入视觉识别、语音或真实状态反馈时，沿相同语义协议扩展。新增感知条件需要在实验中单独报告。

## 执行入口

GOAL_EXECUTION_PROMPT.md 已包含完整阶段、停止条件和三次独立校验要求。AGENTS.md 给出研究与服务器边界。执行者应先读这两份文件，再按 04 至 07 号详细协议实施。

# 05  开发资源与复现入口

[R08] [Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B)。官方模型卡；访问 2026-09-15。第一阶段本地模型；按官方接口关闭 thinking 并输出结构化结果。

[R09] [Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B)。官方模型卡；访问 2026-09-15。在资源审查后开展的另一组模型实验。

[R10] [vLLM Qwen3.5 deployment recipe](https://docs.vllm.ai/projects/recipes/en/latest/Qwen/Qwen3.5.html)。官方文档；访问 2026-09-15。引擎兼容性、启动参数和非思考模式依据。

[R11] [LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)。官方文档；访问 2026-09-15。图内暂停与恢复；应用需另外处理外部抢占与重复副作用。

[R12] [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)。官方文档；访问 2026-09-15。本项目用 SQLite 保持任务状态，避免双份权威状态。

[R13] [smolagents Customize Agent Plan Interactively](https://huggingface.co/docs/smolagents/examples/plan_customization)。官方示例；访问 2026-09-15。轻量 Agent 的计划审阅和修改实现。

[R14] [Viser](https://github.com/viser-project/viser)。官方代码与文档；访问 2026-09-15。Python 驱动网页三维场景和交互控件。

[R15] [Blender MCP](https://github.com/ahujasid/blender-mcp)。社区项目；访问 2026-09-15。适合资产创建探索；执行任意 Python 的能力需要隔离。

[R16] [BlenderProc](https://github.com/DLR-RM/BlenderProc)。官方项目；访问 2026-09-15。批量生成 RGB、深度和标注，作为后续数据准备工具。

[R18] [Viser mesh example](https://viser.studio/main/examples/scene/meshes/)。官方示例；访问 2026-09-15。GLB 资产和网格显示的 API 依据。

这些资料用于理解和适配接口。具体依赖版本以 4029 实际通过的环境为准，并保存 resolved requirements。失败、参数变更和模型更换保留原始记录，便于区分代码问题、环境问题与模型能力。
