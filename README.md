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

网页在服务器环回端口 8780，API 在 8750，本地模型在 8000。客户端通过 SSH 隧道访问；不默认开放到公网。Blender 官方场景构建运行 `scripts/scenes/build_all.sh`（默认全部场景，也可传场景名单）生成 `.blend` 与标注渲染。

## 阶段一的显示定义

Viser 显示对象、几何提示、任务状态和示意焦点面板。Gaussian 数量守恒，σ 暂用有版本的相对配置。焦点面板为设计预览，光学数据由合作者后续提供。场景几何来自已知清单，原型的感知条件记录为已知场景输入。

固定资产采用 CC0；代码按 `LICENSE` 使用。第三方代码、软件、模型权重和字体均未打入文件包。模型下载与源服务器拷贝入口已提供。

## 场景扩展轮（2026-09-17,v2）

在 v1 三场景之外新增五个完全不同的任务场景,设计与验收依据见 `docs/09_新场景与任务设计.md`(经两轮独立设计评审修订):`server_rack` 数据机柜排障、`drone_bench` 无人机检修台、`shelf_picking` 仓储分拣站、`optical_bench` 光具座同轴校准、`dig_site` 考古探方发掘。每个场景沿视轴 ≥0.4m 调焦距离差分层,单场景至少覆盖两档深度需求,五场景整体覆盖 precise/persistent/neutral 全部三档;对象数 5–8。

- 场景 schema 向后兼容扩展:`environment`(仅渲染的环境道具,不进入 LLM 提示词)与 `render_hints`(ortho_scale/grid_extent/cue_scale/label_offset/fit_camera),`schemas/scene.schema.json` 同步再生成。
- 成套 CC0 素材:PolyHaven 26 模型 + 13 纹理下载至 `assets/downloads/`(逐文件 md5 校验,来源与许可见 `assets/downloads/SOURCES.md`),加工为纹理内嵌 GLB 于 `assets/meshes/env/`;v2 交互对象程序化建模于 `assets/meshes/<scene>/`。建模脚本在 `scripts/scenes/`,每个场景经 ≥3 轮独立 SubAgent 视觉审核(`runs/scene_v2/REVIEW_CHECKLIST.md`)。
- 既有缺陷修复(依据 `runs/BUGFIXES_v2.md`):项目 GLB 统一 Z-up 直存约定(修复 Blender 渲染中对象横躺/偏位)、离线渲染 PIL 标签、补光灯追踪 look_at、资产原点守卫 `scripts/assets_v2/check_origins.py`。
- Viser 界面优化:控制面板标签页化 + 操作按钮组;`fit_camera` 按场景包围盒自动取景。

## 发动机舱维修复刻轮（2026-09-17,v3）

复刻用户提供的 AR 发动机维修参考图（横置直列四缸发动机装在开启引擎盖的机舱内、技师拆进气软管卡箍、车库工位；不建人物），新增第六个 v2 级场景 `engine_bay`，设计与 as-built 见 `docs/10_发动机维修复刻场景.md`。六个交互对象（卡箍 CLAMP rotate 90°/火花塞 PLUG insert→PLUGPORT.insertion 锚/机油盖/张紧轮/变速箱侧连接器 CONN inspect_back），相机视轴五层深度 1.47→2.30m（跨度 0.83m），覆盖 precise/persistent 两档。

- 成套 CC0 素材：PolyHaven 29 模型 + 2 HDRI 下载至 `assets/raw/engine_round/`（逐文件 md5，来源与许可见其 SOURCES.md）。开放许可渠道（PolyHaven/Kenney/Quaternius/4028 Models）经检索确认无发动机整机，EA888 风格发动机+机舱+开盖为程序化手工建模。
- 渲染管线修复与扩展：`render_hints.fill_lights`（可选舱内补光，官方渲染死黑 15.7%→0.01%；fill_lights 为纯增量——无该键时走 legacy 三点灯公式，契约层 v1 等价由测试锁定，渲染路径的其余历史变化见 `runs/BUGFIXES_v2.md`；`schemas/scene.schema.json` 同步再生成）；标注避让升级为不动点迭代（该改动曾引入缩进缺陷致六标签只绘一，终审 A 发现后修复：绘制移至碰撞解算之后逐标签绘制）；建模脚本新增标签视线投射断言（6 标签×21 视线对全部 mesh BVH 求交零遮挡）；修复 `_rot_world` 缺 `view_layer.update()` 导致引擎盖铰链从原点旋转的构建 bug。
- Viser 修复（viser 1.1.1 适配）：标签页组不可作上下文管理器（原启动即崩）、按钮组 `on_click` 收到 `GuiEvent`（原四按钮全部静默失效）、`fit_camera` 改按任务对象包围盒取景（原含远端环境件会把相机推远至 13.4m）。
- 提示词第 6-9 轮迭代（`runs/engine_round/prompt_iteration.md`，最终 sha256 20b2988b…）：补"改参=replace（旧计划不进挂起栈）"与"临时任务完成=complete"规则（iter1-3，曾引入 complete_temp 回归并经 A/B 归位），收官审查后例句中性化——不含任何场景对象名与测试输入原句（iter4）。最终状态双绿：`engine_bay` live E2E 5/5（打断/恢复/改参/能力违规，N=6000 守恒，`runs/engine_round/live_engine_round_v5.json`）；`live_extended` 回归 15/15（`runs/engine_round/live_extended_iter4.json`；中间轮回归与 A/B 定位全部留痕）。
- 视频：Blender 飞穿 `runs/scene_v2/videos/engine_bay_flythrough.mp4`（16s/384 帧，五个深度层，中文字幕，GPU OptiX 物理GPU2 经 resource_guard，渲染日志同目录 `engine_bay_render.log`）；Viser 前端演示 `runs/engine_round/engine_bay_viser_demo.mp4`（129s，固定机位无运镜，GUI 真实交互，含大模型 assistant_message 与 cue 点云/ghost 演示，最终 prompt 下录制，meta 见同目录 `_meta.json`）。



第一阶段已在 4029 现场闭环完成。模型为 Qwen3.5-4B（自 4028 `/home/g203-4028/Models` 只读 rsync 复制，`scripts/validate_model_dir.py` 元数据与分片长度校验通过），vLLM 0.29.0 + torch 2.13.0（CUDA 13.0 运行时，驱动 595.91），物理 GPU 1（`GPU-7ba69fc7-12ac-3dfb-8265-3476ce2504b6`），经 `resource_guard.py` UUID 掩码启动；因系统 nvcc 12.1 无法编译 flashinfer 0.6.18 的 JIT 采样算子，采用 `VLLM_USE_FLASHINFER_SAMPLER=0` 的有记录适配。

现场结果：核心测试 38 passed（LangGraph 已安装，集成测试实跑）；live_smoke 三场景通过（预算守恒 6000/6000）；live_interrupt 打断-恢复通过（task_id 与 30 度参数保留）；docs/05 扩展输入 15/15 通过（提示词迭代 5 轮，全部留痕于 `runs/live_extended_attempt*.json`）；模型断连错误可见、动作冻结；服务重启保留任务。规划延迟中位数 3.83 s（20 样本，p90 6.79 s）。证据在 `runs/`（截图、视频、帧序列、原始模型请求与响应、守卫日志）。三次独立 SubAgent 审查记录在 `runs/reviews/`。`verification/LOCAL_VALIDATION.md` 仍描述交付时环境，范围以本节现场记录为准。
