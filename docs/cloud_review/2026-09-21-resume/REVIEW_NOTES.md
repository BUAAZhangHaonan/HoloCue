# 本次续跑审阅说明

首先阅读本目录 FINAL_SUMMARY.md、RESOURCE_STOP.json、COVERAGE.json。应用源码与资产未变化；本次新增 CNC 十八阶段完整通过，以及 connector 初次模型请求失败的原始记录。

八场原生流程目前仅 blocks（此前13阶段）与 CNC（本次18阶段）完成。connector 已尝试失败，其他五场与三组定向配对未运行。按实际内存守卫条件停止实验，不补造结果。

旧 batch 为 runs/simulation/cloud_update_20260921_ce64aff5，旧 ZIP 已封存；其 execution、测试和截图继续按各自 source/asset 身份解释。新 selection 给旧 run_id 添加 previous_，标记 historical/recorded，原始返回码和报告不变。inherited_evidence_verification.json 核验旧路径字节与已封存 ZIP MANIFEST 一致。

当前 batch 为 runs/simulation/cloud_resume_20260921_ea8c2f7。RESOURCE_STOP 记录真实模型守卫越界。model 返回码1是资源停止；api/viewer关闭结果结合 shutdown 阅读。stopped_boundary_check 返回码1是对已关闭模型的预期拒绝。不要把所有非零码合并解释为应用功能失败或全部测试通过。

run_remaining_executed.sh 保存本次实际执行的旧队列，SHA256为1ed7dc0d3b224f4e4e38bbb739de71171b0c119ab1076cc99fe97a72e6aa1ad3。当前续跑工具增加边界服务检查；未经新的授权和资源核验不要重启。CNC 的已完成结果不需要重复运行。

独立报告：code_review.md、provenance_review.md、visual_review.md；辅助选择器专项报告 helper_review.md。图片范围以 visual_review_manifest.json 为准，不把旧图片计入本次新增数量。来源和完整 ZIP 成员检查以 provenance_archive_review.json 为准。

已知视觉边界：CNC接收端内孔和提示上部可见性仍不完整；POCKET9 detail 为占用状态；此前 blocks 标签连接线间隔保留。原生状态同步与两端一致性通过不代表以上视觉问题已经修复。

所有导出的模型回复都来自实际运行；connector 连接失败没有伪造 assistant 回答。中间分层 PNG 可以从原执行目录读取，交付包保留最终原始合成图片、分层 manifest、状态、命令和日志。原始两个新 WebM 均小于47 MiB，无重新编码。
