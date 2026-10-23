# 当前应用接口

API 从 `scripts/run_simulation.sh api` 启动，默认地址为 `http://127.0.0.1:8750`。运行时采用真实本地模型。`HOLOCUE_SCENE_SET=legacy|reconstructed` 或 `--scene-set` 选择场景版本，默认 reconstructed；API 与 Viser 使用相同选择，`/health` 返回 scene_set。设置 `HOLOCUE_API_KEY` 后，请求使用 `Authorization: Bearer <token>`；密钥不进入代码或证据截图。

## 会话与异步任务

| 方法与路径 | 用途 |
|---|---|
| `GET /health` | 查询服务状态与后端模式 |
| `GET /api/v1/scenes` | 列出当前场景 |
| `GET /api/v1/scenes/{scene_id}` | 读取场景契约 |
| `POST /api/v1/sessions` | 以 `scene_id` 创建独立会话 |
| `GET /api/v1/sessions/{sid}` | 读取持久任务状态 |
| `POST /api/v1/sessions/{sid}/messages` | 提交自然语言指令并返回异步任务 |
| `GET /api/v1/jobs/{jid}` | 读取模型请求的执行状态和结果 |
| `POST /api/v1/sessions/{sid}/control/{operation}` | 执行 `pause`、`resume` 或 `complete` |
| `GET /api/v1/sessions/{sid}/snapshot` | 原子读取状态与对应显示包 |
| `GET /api/v1/sessions/{sid}/display` | 读取显示包 |
| `GET /api/v1/sessions/{sid}/events` | 读取会话事件 |

提交消息前读取最新 `revision`。消息包含 `text`、唯一 `request_id` 和 `expected_revision`；控制请求包含 `expected_revision`。重复请求和版本竞争由持久状态层处理。HTTP 409 表示版本冲突，HTTP 422 表示输入或领域约束错误；客户端显示错误并重新读取状态。

消息提交返回 HTTP 202；随后读取返回任务标识对应的 `/jobs/{jid}`。只有任务进入 `done` 才能读取成功模型结果；其他终止状态保留错误。发起新的模型请求时旧动作停止，过期请求不得提交现行计划。模型原始请求与回复保存在实际运行记录中。

## 显示与确认

客户端优先读取 `snapshot`，在同一版本下取得 `state` 与 `display`。`revision` 和 `epoch` 用于识别状态变化、拒绝旧结果和停止过期动作。状态与显示包都包含 scene_set。默认会话库位于 runs/simulation/<scene-set>/state.sqlite；显式 RUN_DIR 可指定一次运行的项目内目录，HOLOCUE_STATE_PATH 可指定其状态文件。场景指纹随版本、配置与资产变化；启动恢复前，API 在同一 SQLite 事务中校验数据库版本标记和全部会话的显式 scene_set，再恢复同版任务。空库可声明版本；已有明确同版会话的库只补充库级版本标记，不改写会话。错版、混合版本、未标明版本或孤立记录的库会使启动失败，原任务、作业与历史保持不变；不自动推断或迁移。运行期间状态、作业和事件读取同样受数据库绑定限制。已有会话与当前几何不一致时创建新会话。

动画运行到终点后等待确认。`complete` 更新任务状态与实体位姿；`pause` 保留进度；`resume` 恢复保存的任务。临时任务与被挂起任务分别保留身份，同一对象的重复动作以独立步骤存储。

## Viser 与 Blender

每个 Viser 连接持有独立会话和视图状态。使用 `scripts/scenes/export_live_frames.py --session <sid> --view-state <path>` 导出该连接的数据帧。导出器检查会话、版本和新鲜度，输出位置为 `runtime_dir()/bridge/<sid>.json`；默认展开为 `runs/simulation/<scene-set>/bridge/<sid>.json`，显式 RUN_DIR 时位于该运行目录。相机记录在同一目录的 viewer/ 下。

打开 `scenes/<scene-set>/<scene_id>/scene.blend`，通过 `scripts/capture/blender_simulation_bridge.py --frame-file <path>` 消费同一数据帧。`--capture <directory>` 和 `--frames <count>` 保存原生帧与版本元数据。实际命令经资源守卫执行，并继承项目内部临时目录设置。

两端使用同一对象位姿、相机、任务时间、提示位置、半径、颜色与不透明度。解析参数及来源见 `configs/preview_response.json`。物理光学接口保留在 `HolographyAdapter` 的 capabilities、submit 与 cancel 契约中，仿真结果使用明确的解析预览标识。
