# HoloCue

任务驱动的全息焦深提示。第一版交付将自然语言任务、可中断状态管理、Gaussian 参数映射和 Blender / Viser 仿真连成一个可扩展原型。

项目目录 `/home/hdd3/zhanghaonan/projects/holocue`。部署服务器 4029。只允许物理 GPU 1、2；其他 GPU 仅允许只读查询，禁止分配计算。

## 从这里开始

把完整文件包交给 Claude Code 或 Codex，先读 `AGENTS.md`，再执行 `GOAL_EXECUTION_PROMPT.md`。该提示词已经规定执行阶段、日志、验收和至少三次独立 SubAgent 复核。

三份说明文档位于 `docs/01_HoloCue_论文思路与系统总览.docx`、`docs/02_给合作者_全息光学调研与交接.docx` 和 `docs/03_给开发者_Agent与仿真环境调研.docx`，并提供同名 Markdown。

## 已包含什么

- 一个严格语义接口，两个 LangGraph 节点，SQLite 任务状态，FastAPI 后端。
- 动态打断、嵌套挂起、角度保留、恢复任务、显式完成和版本化提交。
- 旋钮、插接、积木三个场景，九组原创 GLB 与 OBJ 资产，三组几何采样池。
- Viser 控制界面、Blender 场景构建和实时桥接脚本。
- Qwen3.5 本地部署入口、资源守卫、模型文件检查和真实模型验收脚本。
- 未来内网光学执行接口，以及独立审查记录的验收门。

## 验证范围

交付环境的核心测试为 **36 passed，1 skipped**。测试覆盖状态、接口、模拟 HTTP 和几何资产；LangGraph 集成测试因依赖未安装而显式跳过。Blender、Viser、真实本地 Qwen 和 4029 的整链运行需要执行者完成。详见 `verification/LOCAL_VALIDATION.md`。

`HOLOCUE_MODE=live` 才调用真实模型。`replay` 是明确标注的固定输入测试路径，不能用来报告模型能力，live 失败不会自动切换到 replay。

## 典型启动顺序

先只读检查环境，再在项目虚拟环境安装应用依赖。以下每项的安全前置检查见执行计划。

```bash
cd /home/hdd3/zhanghaonan/projects/holocue
python scripts/inspect_server.py
bash scripts/setup_app.sh
.venv/bin/python -m pytest -q
# 另建 .venv-model，核查 vLLM 或 SGLang 对 Qwen3.5 的支持
# 选择已有模型或执行 prepare_model.sh，禁止未检查就下载重复权重
MODEL_SIZE=4B GPUS=1 ENGINE=vllm bash scripts/serve_model.sh
# 在另外的受管理终端启动
HOLOCUE_MODE=live bash scripts/run_api.sh
bash scripts/run_viewer.sh
```

网页在服务器环回端口 8780，API 在 8750，本地模型在 8000。客户端通过 SSH 隧道访问；不默认开放到公网。Blender 可另行运行 `scripts/build_blender.sh` 生成三个 `.blend` 场景。

## 阶段一的显示定义

Viser 显示对象、几何提示、任务状态和示意焦点面板。Gaussian 数量守恒，σ 暂用有版本的相对配置。焦点面板为设计预览，光学数据由合作者后续提供。场景几何来自已知清单，原型的感知条件记录为已知场景输入。

固定资产采用 CC0；代码按 `LICENSE` 使用。第三方代码、软件、模型权重和字体均未打入文件包。模型下载与源服务器拷贝入口已提供。

## 4029 现场执行状态（2026-09-16）

第一阶段已在 4029 现场闭环完成。模型为 Qwen3.5-4B（自 4028 `/home/g203-4028/Models` 只读 rsync 复制，`scripts/validate_model_dir.py` 元数据与分片长度校验通过），vLLM 0.29.0 + torch 2.13.0（CUDA 13.0 运行时，驱动 595.91），物理 GPU 1（`GPU-7ba69fc7-12ac-3dfb-8265-3476ce2504b6`），经 `resource_guard.py` UUID 掩码启动；因系统 nvcc 12.1 无法编译 flashinfer 0.6.18 的 JIT 采样算子，采用 `VLLM_USE_FLASHINFER_SAMPLER=0` 的有记录适配。

现场结果：核心测试 38 passed（LangGraph 已安装，集成测试实跑）；live_smoke 三场景通过（预算守恒 6000/6000）；live_interrupt 打断-恢复通过（task_id 与 30 度参数保留）；docs/05 扩展输入 15/15 通过（提示词迭代 5 轮，全部留痕于 `runs/live_extended_attempt*.json`）；模型断连错误可见、动作冻结；服务重启保留任务。规划延迟中位数 3.83 s（20 样本，p90 6.79 s）。证据在 `runs/`（截图、视频、帧序列、原始模型请求与响应、守卫日志）。三次独立 SubAgent 审查记录在 `runs/reviews/`。`verification/LOCAL_VALIDATION.md` 仍描述交付时环境，范围以本节现场记录为准。
