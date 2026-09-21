# HoloCue Cloud Update 最终交付记录

日期：2026-09-21。项目：4029 `/home/hdd3/zhanghaonan/projects/holocue`。
本批按 Cloud Update 包限定范围合并和验证。以下数量来自实际执行文件，历史材料保留原始身份。

本批因实际主机内存守卫触发而停止实验并交付资料。完整 pytest 最新记录为 519 项通过；八场原生任务中 blocks 完整通过，CNC 保留 9 个通过捕获阶段后中断，另六场未运行。三组定向配对未运行，不能宣称本包全部原生验收通过。

## 实现与提交

已合并严格 GLB 格式验证、材质分区、工作区域标签和 Session 状态说明；导入四份校验后的 GLB，并构建 engine_bay、shelf_picking、drone_bench 三份原生场景。
修复独立审查和真实页面检查发现的窄窗口异常、跟随对象同步、标签重复切换问题；原生审计增加真实相机同步等待。保留已有 CLAMP、L1/L2、镜面环境方向和固定 fixture 字节。
实现提交截至 `ca213c5d6ea9bd3b9dc7f175cac7aefb7df22ff0`，十个细分提交已推送。文档和最终证据索引的后续提交见实际提交回执。

## 实际测试

| 检查 | 结果 |
|---|---|
| pytest_final.xml | 519 项，失败 0，错误 0，跳过 0；返回码 0；原运行源码 bd938aafb0b6 |
| pytest_final2.xml | 519 项，失败 0，错误 0，跳过 0；返回码 0；原运行源码 b2c379ba354c |
| pytest_results.xml | 495 项，失败 0，错误 0，跳过 0；返回码 0；原运行源码 144eb217ca91 |
| 有序几何动作 | 18 条；1536 点、seed 4701、41 时刻、0.75 毫米阈值；原始报告及摘要在 COVERAGE.json |
| 标签页面 | 12 场景真实宽窄窗口、重复选择、特写/检查隐藏与恢复；blocks 来自 labels_final，其余 11 场景来自 labels_final_r2 |
| 真实 Qwen 专项 | L1→POST2、SPARE→SLOT4、B30 暂停/临时检查 C/明确完成/恢复，以及跟随开关行为；原始回复与状态已保存 |

## 本批原生流程

| 场景 | 本批完整流程 | 阶段数 |
|---|---|---|
| blocks | 通过，返回码 0 | 13 |
| cnc_toolchange | 未通过，返回码 1 | 9 |
| connector | 未运行 | 0 |
| control_panel | 未运行 | 0 |
| dig_site | 未运行 | 0 |
| dive_fillstation | 未运行 | 0 |
| drone_bench | 未运行 | 0 |
| infusion_ward | 未运行 | 0 |

完整通过 1/8 场景，共 13 个通过批次中的捕获阶段。初次 blocks 的失败阶段另行保存，不计入通过数。

## 更新部位配对图

| 场景 | 实际状态 |
|---|---|
| engine_bay | 未运行 |
| shelf_picking | 未运行 |
| dig_site | 未运行 |

## 剩余限制与未运行

- blocks 的 B 标签连接线与文字之间存在局部间隔，独立视觉审查记录为 P3。窄屏主要对象可见，但几何较小。
- CNC 接收位置配对图主要显示侧壁，内孔不可见，提示上部超出画面；不能作为空孔可见性通过证据。
- 其余九份 .blend 保留历史构建来源；本批没有重新构建这些静态文件。
- 全部十二场景的同一最终源码完整原生验收未在本批执行；规定之外的四场景历史流程单独保存。
- 没有真实光学标定、实物系统、用户研究或游戏级质量认证；光学响应为解析 Gaussian 预览模型。
- 较早失败批次的所有辅助脚本历史修订未逐份封存；导出当前辅助脚本与实际运行日志，明确该重现边界。
- viewer 日志中有两次客户端断开时的线程提交到已关闭 executor 异常；独立审查记录为清理竞态，未扩大修改范围。
- cnc_toolchange 原生流程未通过：Exporter stopped during native Blender capture
- connector 完整原生流程
- control_panel 完整原生流程
- dig_site 完整原生流程
- dive_fillstation 完整原生流程
- drone_bench 完整原生流程
- infusion_ward 完整原生流程
- engine_bay 更新部位配对检查
- shelf_picking 更新部位配对检查
- dig_site 更新部位配对检查

### 资源守卫实际停止

2026-09-21T09:09:07.559798+00:00，主机可用内存 50.027195 GiB，低于 50.309079 GiB 保留阈值。API 守卫停止自身进程组，CNC 导出器随后连接失败。按包内资源规则停止全部后续实验，阈值没有修改，也没有重启重试。
CNC 最新批次保留 9 个已验证阶段及中断阶段的文件；整场列为未通过。剩余六场完整原生和三组定向配对列为未运行。详见 RESOURCE_STOP.json、原始守卫日志和执行返回码。

## 来源、独立审查与停止记录

源码摘要：`37b81f92c4bb91b5ca68180be99b1f1810b40657842cf2d3145bd1eeb8d3f0fe`。资产摘要：`36866cf33627a522897a66a3e1247587608d72959dc792d029de0136a0b78af8`。
各检查自身的源码、资产摘要和命令记录见 COVERAGE.json；tools 目录另有 source_supplement.json。三份独立审查报告及实际查看图像哈希一并交付。
本批服务已按记录的 PID 和创建时间停止；8000、8750、8780 端口关闭。详见 service_shutdown.json 与 shutdown_gpu_ports.json。

## 上传文件

UPLOAD_INDEX.json 和 SHA256SUMS 列出全部独立 ZIP 及校验值；本地 UPLOAD_FILES.md 提供逐份绝对路径。每个 ZIP 小于 48 MiB。
资料包括当前代码与配置、验证器及锁文件、实际活动 GLB 和固定 fixture、三份新 .blend、原始截图、模型回复、执行日志、测试 XML、构建来源、资源记录和原始会话录像；完整 blocks 流程与中断记录分别保留。
