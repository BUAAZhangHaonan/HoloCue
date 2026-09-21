# HoloCue 续跑交付记录

日期：2026-09-21。服务器项目：`4029:/home/hdd3/zhanghaonan/projects/holocue`。
本批目录：`runs/simulation/cloud_resume_20260921_ea8c2f7`。

本次新增 CNC 完整原生流程通过，十八个阶段均完成。connector 的首次真实模型请求失败，后续五场景和三组定向配对未运行。原因是共享主机内存再次触发原资源守卫，按包内规则停止实验并交付已有结果。不能宣称本包全部验收通过。

## 本次实际结果

| 项目 | 结果 |
|---|---|
| cnc_toolchange | 完整通过，返回码 0，18 个原生捕获阶段 |
| connector | 返回码 1，PlannerError ConnectError，0 个捕获阶段 |
| control_panel、dig_site、dive_fillstation、drone_bench、infusion_ward | 未运行 |
| engine_bay、shelf_picking、dig_site 定向配对 | 未运行 |
| 服务就绪 | 模型、API、Viser 均实际返回 200；CNC 使用真实本地 Qwen |
| 停止后的队列检查 | 预期返回码 1，明确拒绝已停止的模型；没有重启服务 |
| 清理 | 22 个记录的进程身份均退出，8000/8750/8780 关闭，GPU 1/2 各 4 MiB |

本包要求的八场完整原生流程，合并此前 blocks 的 13 阶段通过，本批新增 CNC 的 18 阶段通过，当前完成 2/8 场。另六场仍需完成；connector 已尝试并失败，另外五场未运行。此前 CNC 的失败与部分通过记录保留原身份。

## 资源停止的实际时序

2026-09-21 12:28:47.636250 UTC（北京时间 20:28:47），模型守卫记录主机可用内存 50.282642 GiB，低于原保留阈值 50.309079 GiB。模型服务停止，返回码 1。CNC 已获得的计划继续执行，12:32:35 UTC 完成；connector 于下一秒启动，首次模型请求因连接失败而结束。

已执行队列仅通过 set -e 检查当前命令，缺少场景之间的独立服务存活检查，因此模型停止后仍发起了一次 connector 检查。已保留原 shell 字节及哈希，并在续跑工具中加入服务 recorder 结束状态、PID、创建时间与 zombie 检查；用已关闭服务实测确认拒绝启动下一阶段。此修复没有改变本次实际失败记录，也没有补跑实验。阶段内部仍由各自资源守卫负责。

后续内存回升不改变本批已触发资源停止的事实。没有降低阈值、更换模型、调整采样协议或占用其他物理 GPU；没有停止其他任务。

## 来源与复用

起始提交：`ea8c2f7838f7bf18fef6e5f64b83e641b5a0962e`。
应用源码摘要：`37b81f92c4bb91b5ca68180be99b1f1810b40657842cf2d3145bd1eeb8d3f0fe`。
资产摘要：`36866cf33627a522897a66a3e1247587608d72959dc792d029de0136a0b78af8`。
本次没有修改应用源码、活动资产或固定 fixture。126 份源码、76 份活动 GLB 和 27 份固定输入记录均与此前封存身份核对一致。辅助编排工具不在应用源码摘要范围，实际文件另外交付。

此前最新完整 pytest 为 519 项通过，源码摘要 b2c379ba354c；18 条几何动作检查和三份原生构建来自源码摘要 144eb217ca91。十二场景标签检查和三组真实 Qwen 专项保留各自执行身份。本次没有重复这些检查，也不将其写成当前摘要下新运行的结果。详见 COVERAGE.json 的 reused_checks、earlier_batch 与原 execution.json。

## 视觉审查与未完成范围

三份独立审查报告、实际查看原图的 SHA256 清单一并提供。CNC 运行完成不等于所有视角均达到视觉要求。接收端视图仍主要显示侧壁，孔内不可见，提示上部裁切；POCKET9 特写是已占用承座，不能验证空孔可见性。此前 blocks 的 B 标签连接线局部间隔等限制保留。

尚需完成 connector、control_panel、dig_site、dive_fillstation、drone_bench、infusion_ward 的完整原生流程，以及 engine_bay、shelf_picking、dig_site 更新部位定向配对。其他历史构建与原生验收保留原来源。解析 Gaussian 响应不提供真实光学标定、实物实验、用户研究或游戏级质量认证。

## 交付与核验

新交付包汇集本次证据和此前封存证据，旧包保持不变。继承的文件逐项核对旧封存 MANIFEST 的大小和 SHA256；当前执行身份同时要求源码前后摘要及资产前后摘要一致。

资料包含原始 Viser/Blender 图片、完整 CNC 会话录像、connector 失败录像、真实模型回复、命令日志与返回码、测试报告、实际 GLB/fixture、选定的三份 .blend、资源及关闭记录。每份 ZIP 小于 48 MiB，独立解压；UPLOAD_INDEX.json、SHA256SUMS 与 UPLOAD_FILES.md 列出校验值及本地绝对路径。最终提交、推送和包核验结果见 FINAL_RECEIPT.json。
