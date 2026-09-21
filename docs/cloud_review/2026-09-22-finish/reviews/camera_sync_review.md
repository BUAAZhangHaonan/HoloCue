# Shelf 相机同步问题独立审查

审查者：`/root/cloud_code_review`。本报告整理已读取的真实失败记录、应用及已安装 Viser 源码和最小候选差异；没有新增实验，没有修改应用或活动工具。

项目为服务器 `/home/hdd3/zhanghaonan/projects/holocue`；以下 RUN 内路径均相对此目录：`runs/simulation/cloud_finish90_20260921_e67b574`。

## 已观察事实：P2

原 `pairs_shelf_picking_command/stderr.log` 显示 `capture_changed_pairs.py:43` 在 `BASKET_endpoint_waiting_confirmation` 调用 `Audit.select_view` 时失败：`Visible focus control did not focus the contracted target plane`。此前两个配对阶段成功；原失败目录保留。

`changed_pairs/shelf_picking/focus_failure.json` 中 session 为 `4f03269ed65e4c328429b2aa43ffe4a2`，状态 revision 3 / epoch 2、已暂停。目标 BASKET 焦点为 `[-0.25,-0.62,0.95]`；相机 position 为 `[0.055712080012865525,-1.1858613019468907,1.1172375157779524]`，look_at 为 `[0.05571208001286554,-1.6476531013682805,1.1172375157779526]`，方向朝向目标相反一侧。计算期望深度 `-0.5658613019468908`，原/实际 focus 仍为 `0.33526764167891876`。

同目录 `view_camera_checks.jsonl`、`api_reads.jsonl`、`focus_actions.jsonl` 与失败快照用于关联相机和操作时序。已读一致性记录显示该错误姿态在约 0.7525 秒、5 个不同导出上满足 Python/实际客户端相机一致，随后等待亦未恢复；这不是仅凭一次旧导出计算的瞬时假失败。`viewer_resume02_command/stderr.log` 同时出现 `viewer_scene.py:245` 的 `ValueError: selected target lies behind camera`。不能通过放宽焦点断言把该次失败算作通过。

前一次成功 BASKET detail 使用相同 position，但 look_at 为 `[-0.25,-0.62,0.91]`；前一个 BLUE inspection 朝向负 Y。BASKET 在当时 cue 中没有自己的目标 cue，局部几何逻辑不要求将其 detail 朝向改为负 Y。

## 已读源码与根因边界

应用旧 `src/holocue/viewer_scene.py:212–214` 分别设置 camera 的 up_direction、position、look_at，未由 `client.atomic()` 合并。`src/holocue/viewer.py:113–120` 的对象下拉回调会立即按当时 view mode 选择视图；`scripts/tests/audit_bridge_live.py:163–165` 先选择对象再点击视图按钮，没有等待对象选择回调完成。

安装源码 `.venv-simulation/lib/python3.12/site-packages/viser/_viser.py` 的 position setter（260–278）除发送 Position 外，还平移 look_at 并发送 LookAt；look_at setter（488–505）有 allclose 短路。ViewerCameraMessage 接收处理（1198–1217）会更新相机状态，不受应用 Operator 锁约束。客户端 `client/src/MessageHandler.tsx` 的 setTarget（541–558）和 setPosition（598–623）分别处理这些消息。

据此，连续 UI 对象/视图切换与分离相机消息、客户端回传之间存在产生混合姿态的合理竞争路径。**源码和实际坏姿态支持同步竞争诊断，但没有逐消息录制证明此次唯一精确交错；不能宣称 atomic 的修复效果已经由此静态分析证明。**

## 最小差异与执行身份

本地候选目录为 `E:/OneDrive/文档/Playground/.work/holocue/cloud_finish90_20260921/camera_fix/`。保存的旧 `viewer_scene.original.py` SHA256 为 `336b53785d732a05e0d3f06712a09b8323effc862a7fa377c4cc498c558bf71a`；候选 `src/holocue/viewer_scene.py` SHA256 为 `98006df1f6b922b58136d814e8ee97d30d94c8505adeede0cd2850c66ed8f331`。精确差异另存 `viewer_scene_atomic.patch`。

唯一应用变化是以 `with self.client.atomic():` 包住原有 up_direction、position、look_at 三次赋值；赋值内容、模型、相机计算、任务、资产和验收阈值不变。主线程已应用该候选，源码阶段从 `c33e1ae4cdd7251c217e61caa31a2d58668984b0db6653d1fe4ac29929862e2a` 转为 `d8d73e7d849b949bfee3827d6f60dfb86351cc50b49f98027b92db1664392806`；资产仍为 `36866cf33627a522897a66a3e1247587608d72959dc792d029de0136a0b78af8`。

主线程已确认新 `pytest_camera_final_command/execution.json` 为 529 passed、0 failed/error/skipped、rc0，record elapsed 246.511 秒。此记录属于 d8；旧 `pytest_final`、live12场30步、response 和十二场视频仍属于 c33，不因补丁而升级身份。

最小真实回归 helper 为 `camera_fix/verify_camera_atomic.py`，在实际 Shelf live 原任务暂停终点执行 10 轮 BLUE inspection→BASKET detail，复用原 `Audit.select_view` 和实际 `CLIENT_READ`，严格检查目标在前、正焦距及契约一致，并保存状态/原始回复/事件/截图/每轮 view；UI 失败即退出，不重试。原配对 helper 另保留字节，仅新 `capture_changed_pairs_attempt.py` 支持显式输出 `RUN/changed_pairs/shelf_picking_attempt02`，不覆盖原失败。

**待填写：`RUN/camera_atomic_live` 的实际 10 轮结果；`pairs_shelf_picking_attempt02_command/execution.json` 与 `changed_pairs/shelf_picking_attempt02/report.json` 的最终结果。** 本报告写入时不把进行中回归声明为通过。
