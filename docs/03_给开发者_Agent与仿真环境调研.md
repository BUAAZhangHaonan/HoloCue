# 开发者实现说明

HoloCue 使用真实本地模型解释自然语言，通过 LangGraph 的解释与场景校验流程生成严格语义计划。SQLite 保存权威任务状态，FastAPI 提供版本化接口，Viser 和 Blender 接收共同的场景与显示数据。

当前实现分工、坐标契约、状态转换与解析响应见 [系统架构](SIMULATION_ARCHITECTURE.md)。HTTP 与桥接参数见 [接口说明](API.md)。源码中的数据协议由 Pydantic 校验，模型提示词保存在 Markdown。

## 任务与并发

模型请求携带场景对象与任务上下文。模型只输出语义字段，确定性模块负责预算、位姿和显示参数。请求使用 revision、epoch 与 request_id 管理版本竞争和幂等；迟到结果不能覆盖现行计划。

同一对象可在有序队列中出现多次。临时检查挂起完整原计划，恢复保持 task_id、参数与进度。动画到达终点等待用户明确完成，完成时更新实体位姿。模型断连、无效输出和过期显示应明确暴露。

每个浏览器连接拥有独立场景、会话、相机与动作时钟。Viser 版本固定为 1.1.1；控件与相机接口需要依据实际安装版本核验。浏览器窗口比例参与观察范围计算。

## 原生显示链

场景使用标准 glTF 资产和统一配置，运行时转换为米制、Z 轴向上的坐标。统一资产构建入口为 `build_simulation_assets.py`，Blender 构建入口为 `scripts/scenes/build_all.sh`。

Viser 视图状态与 API snapshot 经 `scripts/scenes/export_live_frames.py` 转换为版本化数据帧，`scripts/capture/blender_simulation_bridge.py` 在当前场景读取该帧。两端使用相同对象位姿、相机、任务时间和提示响应参数。

解析 Gaussian 响应由 `configs/preview_response.json` 定义。焦点、亮度、数量与 sigma 影响实际三维提示。当前解析预览的证据范围与后续光学标定见系统架构，保留 `HolographyAdapter` 接口。

## 环境与验证

应用使用 `.venv-simulation`，模型使用已经验证的独立 Qwen3.5-4B 环境，Blender 复用服务器安装。只允许物理 GPU 1、2；资源守卫采用现场与项目限制中更严格者。所有安装、测试、浏览器与 Blender 启动前设置项目内部临时目录和缓存，命令见 [README](../README.md)。

依据 [验证标准](VALIDATION.md) 完成十二场景真实模型、原生视觉、同会话桥接、两客户端隔离、持久恢复和错误处理。独立审查与最终报告必须对应实际最终代码与证据，不以历史测试数量表示当前版本完成。
