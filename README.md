# HoloCue

HoloCue 将真实本地模型的任务解释、持久任务状态与十二场景三维提示连接起来。模型输出对象、动作、任务角色、优先级和深度需求；确定性模块计算显示预算、对象位姿与解析 Gaussian 响应。

当前设计见 [系统架构](docs/SIMULATION_ARCHITECTURE.md)、[场景约定](docs/SCENE_REVIEW.md)、[接口说明](docs/API.md) 和 [验证标准](docs/VALIDATION.md)。既有研究资料保留原文。实际完成状态以本次验收目录中的原始记录与最终报告为准。

## 运行环境

服务器项目目录为 `/home/hdd3/zhanghaonan/projects/holocue`。只允许物理 GPU 1、2；复用已有 Qwen3.5-4B 模型环境与 Blender。应用使用独立的 `.venv-simulation`，Viser 版本固定为 1.1.1。启动前读取现场资源规则与 `scripts/guard/resource_guard.py`，采用更严格的限制。

任何安装器、浏览器、Blender 或测试程序启动前，先设置项目内部临时目录与缓存：

```bash
cd /home/hdd3/zhanghaonan/projects/holocue
export TMPDIR="$PWD/.work/tmp"
export TMP="$TMPDIR"
export TEMP="$TMPDIR"
export XDG_CACHE_HOME="$PWD/.work/cache"
export PIP_CACHE_DIR="$PWD/.work/cache/pip"
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.work/browsers"
export PYTHONPYCACHEPREFIX="$PWD/.work/pycache"
export HOLOCUE_ROOT="$PWD"
export PYTHONPATH="$PWD/src:$PWD"
mkdir -p "$TMPDIR" "$XDG_CACHE_HOME" "$PIP_CACHE_DIR" "$PLAYWRIGHT_BROWSERS_PATH" "$PYTHONPYCACHEPREFIX" runs/simulation
```

Python 字节码写入 `.work/pycache`，pytest 的运行缓存由 `pyproject.toml` 定位到 `.work/pytest-cache`。应用与模型入口在启动 Python 前设置字节码缓存目录，资源守卫也将该目录传给执行子进程。

使用已核验的 Python 3.11 或更新版本创建应用环境并安装项目依赖；已有环境先检查再使用：

```bash
python3 -m venv .venv-simulation
export APP_PYTHON="$PWD/.venv-simulation/bin/python"
"$APP_PYTHON" -m pip install -e '.[dev,simulation]'
"$APP_PYTHON" -m pip freeze > runs/simulation/app_requirements.txt
```

设置 `HOLOCUE_MODEL_URL` 与 `HOLOCUE_MODEL_NAME` 为已经验证的本地模型服务配置。模型名称、端点、权重目录和引擎版本记录在验收目录。模型启动脚本位于 `scripts/ops/`，已有模型服务优先复用。应用仅支持 live 模型。

分别在受管理终端启动两个服务并记录进程归属：

```bash
bash scripts/run_simulation.sh api
bash scripts/run_simulation.sh viewer
```

API 默认监听 `127.0.0.1:8750`，Viser 默认监听 `127.0.0.1:8780`。启动前核对端口归属。客户端使用 SSH 隧道：

```bash
ssh -N -L 8750:127.0.0.1:8750 -L 8780:127.0.0.1:8780 4029
```

浏览器打开 `http://127.0.0.1:8780`。只停止本次启动并记录的进程。

## 场景与资产

`scenes/<id>/scene.json` 是对象、尺寸、位姿、动作轴、接合终点、检查面和任务验收的共同契约。交互对象与环境资产位于各场景的 `meshes/`。资产采用标准 glTF 坐标，运行时转换为米制、Z 轴向上的世界坐标。已有有效资产及其许可、来源和实验记录保留。

对象可通过 `interaction.detail_direction_local` 指定目标特写的观察方向。该方向是对象局部坐标中的单位向量，指向相机，并随对象位姿旋转；未指定时使用场景观察方向。旋转任务沿动作轴取景，结构检查使用既有检查面，两者优先于这个普通特写方向。发动机舱插孔沿局部正 Z 方向观察，使安装后的内圈避开前方支撑筋的遮挡。

`scripts/scenes/build_simulation_assets.py` 根据场景契约与 `modeling.py` 生成资产。该命令会更新场景网格，执行前核对本次修改范围与已有细节。

设置 `BLENDER_BIN` 为已存在的 Blender 可执行文件后，统一构建全部场景：

```bash
bash scripts/scenes/build_all.sh
"$APP_PYTHON" scripts/scenes/check_scene_kit.py --require-blender
```

构建链使用 `export_blender_payload.py` 和 `build_blender_scene.py`，产物为每个场景的 `scene.blend` 与原生图像。场景列表由配置目录枚举。

## 交互与同会话桥接

每个浏览器连接拥有独立的会话、场景、相机和任务时间。动画到达终点后等待明确完成；确认后更新实体位姿。临时检查保留原任务标识、参数和进度。同一对象的连续动作保留为独立有序步骤。

`configs/preview_response.json` 提供解析响应参数。焦点、亮度、Gaussian 数量和 sigma 参与实际三维提示生成。该响应的标识为 `analytic_gaussian_preview`，物理光学标定由保留的适配器接口提供。

Viser 使用方向光、强度为 0.1 的 studio 环境补光和资产原有材质。默认级联投影阴影关闭，近距离检查依靠实体几何、表面明暗和材质反射显示结构与文字。Blender 保留原生场景照明和投影阴影。两端照明效果分别验收，三维提示继续使用共同的解析响应参数。

Blender 桥接使用 `scripts/scenes/export_live_frames.py` 导出当前会话与对应连接的视图状态，再由 `scripts/capture/blender_simulation_bridge.py` 读取。两端共享对象位姿、相机、提示中心、半径、颜色、不透明度与任务时间。导出器要求 `--session` 和 `--view-state` 属于同一连接，过期或版本不一致的数据应明确报错。

## 验收与证据

按照 [验证标准](docs/VALIDATION.md) 执行全部有效测试、几何检查、十二场景真实模型流程、原生 Viser 浏览器操作与 Blender 同会话桥接。必须覆盖宽屏与较窄窗口、两客户端隔离、显示响应、状态恢复和错误处理。

三份独立审查分别覆盖场景视觉、状态任务、架构与运行安全，并对应同一份最终代码。新的验收目录保存代码摘要、依赖与模型版本、资源记录、真实请求、图像和视频、执行命令、审查原始输出与未解决问题。历史 `runs/` 中的证据保持原样；它们不自动代表当前版本已通过验收。
