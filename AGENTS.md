# HoloCue 执行约束

## 研究定义

主线是任务驱动的全息焦深提示。LLM 输出任务角色、优先级、深度需求、对象与动作；确定性模块生成 Gaussian 数量与显示配置。现阶段 σ 为相对示意参数。实体深度和姿态来自场景或经标定的感知输入。

不得自行改变研究定义、增加资源调度网络、把 Gaussian 数量变成 LLM 自由输出、把示意模糊写成物理实验，或把一次演示写成论文结论。可以修复明确代码缺陷、适配经核验的 API，并留下修改与测试依据。

## 服务器与文件

4029 项目仅限 `/home/hdd3/zhanghaonan/projects/holocue`。允许在项目内新建虚拟环境、缓存、日志、资产与模型目录。复用 Blender，禁止系统级升级、sudo 安装、修改其他项目或覆盖已有仓库历史。

4028 的 `/home/g203-4028/Models` 只读查找与复制。SSH 别名、用户名和具体 checkpoint 路径从现有配置只读确认，不能猜造连接信息。优先复用完整同名模型；不清理源目录。

只允许物理 GPU 1、2。GPU UUID 掩码由 `resource_guard.py` 确认。逻辑 cuda:0 仅能表示获准物理 GPU 在掩码内的重映射。Blender 和 Viser 阶段一默认 CPU。

内存阈值先读取真实服务器规则，采用与包内默认值中更严格者。不得杀其他用户进程、重置 GPU、关闭内存监控、扩大到其他 GPU 或静默缩换模型。资源不足时保留证据并停止受影响阶段。

## 工程约束

所有新增或修改的源码必须运行统一格式化入口并通过检查后提交：
`python scripts/format_code.py`，随后 `python scripts/format_code.py --check`。
Python 使用项目固定版本的 Ruff；JavaScript/TypeScript 与 Shell 使用
`tools/formatting/package-lock.json` 固定的 Prettier 和 Shell 插件。
首次准备运行 `python -m pip install -e '.[dev]'` 与
`npm ci --prefix tools/formatting --cache .work/cache/npm-formatting`。
格式化范围由 Git 可见源码确定；忽略目录中的历史证据、原始 fixture 字节和生成产物保持原样。
格式检查失败时必须修正，不能跳过检查或手动修改封存材料满足格式要求。

所有模型提示词保存在 Markdown，数据协议经过 Pydantic 校验。模型输出错误须保留原始结果并可见报错，禁止自动用固定脚本补上正确答案。重规划先停止旧动作，再提交新版本。过期响应无法覆盖现行计划。用户点击确认完成才推进任务，动画播放结束不等于真实操作完成。

API 默认环回，远程访问用 SSH。后续内网模式需要配置认证和明确网络策略。密钥不得写入 Git、截图或报告。工具执行不接收任意 Python 或 shell 字符串。

## 收官

遵循 `GOAL_EXECUTION_PROMPT.md`。必须调用至少三个独立 SubAgent 会话完成不同审查，其中至少一位具有视觉能力并实际查看渲染与交互证据。每次修复后，受影响审查必须重跑；最终三份报告都对应最后代码摘要。无法调用 SubAgent 时明确记录阻塞，不得由主 Agent 写三份自评冒充独立验证。
