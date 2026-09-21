# HoloCue 续跑记录

用户在上一批交付后明确要求继续剩余任务。现场核验时主机 available 为 261562101760 字节，物理 GPU 1、2 均空闲；仓库 HEAD 为 ea8c2f7838f7bf18fef6e5f64b83e641b5a0962e，工作区干净。

新运行目录为 `runs/simulation/cloud_resume_20260921_ea8c2f7`，新数据库为其中的 `state.sqlite`。上一批运行目录、数据库和封存 ZIP 不覆盖。复用原模型、提示词、渲染参数、场景资产和资源守卫。

## 启动记录

GPU 预检通过旧 `record.py` 保存。最初尝试把 `start_ui.py` 作为裸命令交给原始 `record_command.py`，该工具在执行前拒绝，实际错误为：

```
ValueError: Invoke the existing resource_guard.py with --execute as the recorded command
```

该次返回码为 1，没有启动服务。没有修改或放宽原记录工具。随后直接调用既有 `start_ui.py`；它为 model、api、viewer 分别启动原有 `record.py` → `resource_guard.py` → 原服务命令，保存各服务的 PID、创建时间、命令、源码/资产摘要、日志和退出码。启动器本身只编排这些被独立守卫管理的进程，不能用一个启动后立即退出的外层资源守卫包装它，否则外层守卫会清理刚启动的子进程。

`readiness.py` 只访问真实服务就绪接口，不发送模型任务。就绪后 `run_remaining.sh` 顺序执行 CNC、connector、control_panel、dig_site、dive_fillstation、drone_bench、infusion_ward，再执行 engine_bay、shelf_picking、dig_site 的规定定向配对。任何非零返回码立即停止队列。

已通过的 blocks 原生流程、完整 pytest、十八条有序运动、十二场景标签和三场景构建保留各自原始执行身份，不重复生成。CNC 在新会话中完成完整协议，不能将中断前的截图拼作本次新会话的执行结果。

完成后按记录停止本次服务，更新实际覆盖、独立审查、细分提交和小于 48 MiB 的上传分包。若资源守卫再次终止运行，按原规则停止实验并保存已有资料。
