# 续跑清单

- [x] 核验当前仓库、资源、物理 GPU 1/2 和空闲端口。
- [x] 独立核验源码 37b81f92、资产 36866cf3 与上一批封存内容一致。
- [x] 建立新 RUN / DB，记录服务 PID 与原模型/守卫参数。
- [x] 真实模型、API、Viser 就绪，CNC 十八阶段完整通过。
- [ ] connector 零阶段失败；control_panel、dig_site、dive_fillstation、drone_bench、infusion_ward 未运行。实际内存守卫停止模型，实验结束。
- [ ] engine_bay、shelf_picking、dig_site 定向配对未运行。
- [x] 三个独立会话审查最终源码、三十六张实际原图、来源和范围；视觉限制保留。
- [x] 停止本次服务，二十二个记录的进程身份均退出，三个端口关闭。
- [ ] 更新覆盖与总结，细分提交并推送。
- [ ] 导出小于 48 MiB 的独立 ZIP，服务器、本地和独立成员哈希核验，交付绝对路径。

文档封存时提交和归档核验仍在进行，最终状态以 ZIP 外的 FINAL_RECEIPT.json、LOCAL_VERIFICATION.json 和 provenance_archive_review.json 为准；以上未完成实验条目保持不变。

当前项目：4029 `/home/hdd3/zhanghaonan/projects/holocue`。
本批 RUN：`runs/simulation/cloud_resume_20260921_ea8c2f7`。
环境：`.work/cloud_resume_20260921/phase_env.sh`。
只读状态：`python .work/cloud_resume_20260921/progress.py`。
实际执行队列原字节：本批 RUN 的 `run_remaining_executed.sh`。当前 `.work/cloud_resume_20260921/run_remaining.sh` 已增加服务边界检查，仅实测了停机拒绝，没有重启实验。
沿用记录、定向配对、关闭服务、进程核查工具：`.work/cloud_update_20260921/`；由新 RUN 环境决定输出位置。

本批初始仓库 `ea8c2f7838f7bf18fef6e5f64b83e641b5a0962e`，应用没有新改动。既有 blocks、519 pytest、几何、标签和构建材料保持原身份；旧18ZIP不修改。完整原生成功批次不重复，具体失败保留证据后只处理受影响范围。
