# 独立审查说明

本说明与 FINAL_SUMMARY.md 共用项目根及 R0–R4 路径定义。结论限真实记录、源码
和已审图像范围；最终封包/下载事实以随附交付清单为准。

## 已处理问题与证据边界

| 问题 | 实际处理/结论 | 原始证据与审查来源 |
| --- | --- | --- |
| 窄窗口标签及同 task_id 重选对象同步 | 已作局部应用修复；重复选择视图另使 annotation_key 失效，避免缓存跳过标签恢复 | 本地 `E:/OneDrive/文档/Playground/.work/holocue/cloud_update_20260921/code_review.md`；对应 R1 运行/标签记录保持原身份 |
| 聚焦验收读取过早的旧相机 | audit harness 要求真实客户端与 Python 相机持续一致 >=.75 秒且 >=3 个不同 generated_at；保留原 CNC/Blocks 失败 | R1 `bridge_batches/{blocks,cnc_toolchange,cnc_toolchange_final}/report.json`；成功分别在 blocks_final 与 R2 CNC，不能把 harness 修复当相机/模型参数变更 |
| 场景边界在服务终止后仍启动下一场 | 后续 helper 增加实际服务 execution/PID/create_time 检查；本次已发生的 connector 0-stage 失败保留 | R2 `bridge_batches/connector/report.json`；R2 旧执行 shell 字节和停止边界检查记录 |
| Viser HDR 透明度停在中间值 | 第二纹理分支补 opacity=1；旧受控测试 1 pass/1 fail，修复 2 pass，构建与安装 rc0，新实际 served build 已核 | `.work/viser_hdr_opacity_fix/REVIEW.md`、`DELIVERY_README.md`；R4 `hdr_opacity_*_command/`、`viser_opacity_install.json`、`hdr_diagnostic_after/` |
| 旧 connector 成片整画布漂白 | attempt01 视觉拒绝；attempt02 的独立代表帧正常，旧录像不覆盖 | `.work/cloud_finish90_20260921/visual_review.md`、`video_review_manifest.json`、`clientfix_visual_manifest.json`；R4 `videos/connector_attempt01` 与 `connector_attempt02` |
| 视频结果/provenance 与失败状态 | workflow 后异常明确复位 passed=false；制作逐场绑定 source/assets/capture SHA；保留旧工具字节 | `.work/cloud_finish90_20260921/video_provenance_review.md`；`.work/cloud_video_20260921/versions/` |
| 安装器路径及最终交付 owner | 安装器限制准确 RUN/source/target/backup，并比固定 SHA；停服产物按实际 action/--generation argv 绑定 | `.work/cloud_finish90_20260921/install_visor_opacity_fix.py`、`delivery_helpers_cross_review.md` |
| Shelf 原配对真实相机 P2 | 前 2 阶段通过，随后负焦深且服务端聚焦报目标在后方；atomic 三赋值修正后真实 10 轮/20 切换与 Shelf attempt03 四阶段通过，闭合限该协议范围 | R4 `changed_pairs/shelf_picking/` 原失败记录、`pairs_shelf_picking_command/stderr.log`；`camera_atomic_live/result.json`、`changed_pairs/shelf_picking_attempt03/report.json`；差异 `.work/cloud_finish90_20260921/camera_fix/viewer_scene_atomic.patch` |

SOURCE_PHASES 必须区分旧 c33e1ae4cdd7251c217e61caa31a2d58668984b0db6653d1fe4ac29929862e2a
与新 d8d73e7d849b949bfee3827d6f60dfb86351cc50b49f98027b92db1664392806，assets 均
36866cf33627a522897a66a3e1247587608d72959dc792d029de0136a0b78af8。唯一应用差异是
viewer_scene.py 的 atomic 三赋值。新 pytest_camera_final 529 项、零失败/错误/跳过，
rc0，record elapsed 246.511 秒；旧 pytest_final 529/live12场30步/response 检查均为
c33 历史结果，不能升级为新 d8 执行。d8 的 10 轮/20 次真实相机切换 rc0，21 张
原图已独立查看；Shelf attempt03 四阶段 passed/rc0，session
57e94d5ad75043fc8c26d0d890cca895。attempt02 因相对 --out 预检拒绝，无目录无图，
不算行为回归失败。修复结论以真实定向回归支持，不以 pytest 单独证明所有竞态消除。

旧图像漂白与像素混合关系支持 HDR 时序根因；部署前被动 DOM 诊断最终达到 1，
未抓到永久 .24，不能说现场 DOM 已确认卡死。缺陷本身由受控实际组件回归证明。
安装后一次实际 served hash/透明度检查通过，也不能推广为所有历史录像均已修复。

## 仍需如实保留的限制

- 标签引线局部遮挡/间距属于已观察 P3；ghost 可遮住接收口，局部目标或外围装置
  可能出画面。代表帧可确认的轮廓、端子、字牌不等于内部接触深度或物理对准测量。
- 光学 M 的亮镜面有可辨边界，不能因不同视角亮暗或指针位置推导精确旋转 15°；
  TRAINING/SIMULATION 字牌与无数值表盘不能解释成真实设备读数或医疗验证。
- response 指标是 Whole-canvas changed pixels。focus 312 像素变化不应描述成
  明显整体失焦、物理焦深验证或空间局部性证据。
- 人工视频审查是清单所列时间点代表帧，不是全片逐帧审阅；全帧 decode/PTS 检查
  证明转码完整性，不证明每一帧画面正确。UI-only 不并入 native 阶段数。
- 已观察到客户端断开时 poll 线程 executor.submit 的 shutdown 清理竞态；保留
  对应 stderr，不据此伪称 UI/session 失败，也不宣称本批已做生命周期重构。

## 失败与资源时间线

R1 保留 Blocks 首次 3 阶段失败、CNC 首次 5 阶段聚焦失败及后续 9 阶段资源中断；
R2 CNC 18 阶段通过，但随后 connector 0 阶段 PlannerError/ConnectError。R3 在
用户授权 90% 已用上限后通过 connector/control/dig；Dive 后续资源中断无完整报告。
R4 Dive 23 阶段通过，首代再次触发 90% 守卫：CNC 制作与 model/api/viewer 记录均
有 host memory reserve reached；Drone 初次 native 完成 2 阶段后内层 Blender guard
停止；Engine UI attempt01 的真实连接拒绝保留。R4 resume01 Drone attempt02 通过
20 阶段；resume02 用于客户端修复后续任务，并完成 Infusion native 19 阶段 rc0，
session 08431a11918d4472bcdbeb17f703b1e3，source c33/assets3686。随后发现 Shelf
定向配对相机 P2，封闭 resume02 后以 d8/resume03 做最小修正验证，旧失败不覆盖。

R4 中断数值、Unix 时间、进程归属详见 R4 `RESOURCE_STOP_01.json`、
`RESOURCE_STOP_01.md`。保留值为 25.15453948974609 GiB；守卫日志的 available
观测低于该值。多守卫时刻不同，不足以归因全机内存均由本任务占用。用户释放其他
任务后继续属于新授权的恢复，不回写旧停止记录。

## 最终交付核对

显式 VIDEO_ACCEPTANCE 要求十二场唯一 accepted production manifest 的 SHA/session，
并保留 rejected 理由。旧 connector 原 raw 和所有 MP4 放入 rejected_attempts，
未选但完整产物放入 retained_attempts。新 capture 用真实主文档 SHA 和 canvas/祖先
opacity 实值核验；旧 capture 未测客户端身份的历史限制不补造。

独立交付 helper 审查发现的停服归属 P2 已闭合。已读实际
`R4/delivery_helpers_validation_04_command/execution.json` rc0，11 组合成检查，
当时 selector SHA `dee5d7fa35811d537bd4b30d5ee951b1f52732f00c9d3399d6d55550abc279f7`。
该合成检查属于其原代码/来源。后续两源码阶段通过显式 SOURCE_PHASES 和 actual --out
归属支持；最新 selector SHA 前缀 `8e2a8c`，`delivery_helpers_validation_07` 33 组合成
检查 passed，实际完整 SHA/执行身份按其记录核对。旧 validation06 的 digest 变量遮蔽
失败及后续修复记录均保留，不改写成首次成功；任何合成检查都不替代最终文件集合验证。
最终必须调用 RUN4 的
`.work/cloud_finish90_20260921/export_review.py`；根已说明它仅为旧打包器增加
`.cjs/.diff/.ts/.tsx` 支持，47 MiB 及其他校验不变；实际 export/verify 结果读取随附
`UPLOAD_INDEX`、`LOCAL_VERIFICATION` 与封包后生成的 `DELIVERY_RESULT.md`。

Infusion native 已确认 19 阶段 rc0（c33/3686）；实际原图视觉范围按最终独立清单列明。

Engine 定向配对 2 阶段、Dig 1 阶段均 rc0/c33。Dig 是初始 FLAG 支撑侧视，不能称
任务完成终点。Shelf attempt03 四阶段通过，八张原图已实际独立查看：空篮、BLUE
面单、等待确认的提示和确认后 RED 入篮均朝向正确；前壁遮住篮底接触面，保留此限制。
原失败、attempt02 预检拒绝和 attempt03 成功分别保留。

十二场视频已全部 c33 完成；26 MP4/251 代表帧包含旧 connector 拒绝片。最终接受
manifest/拒绝列表以随附 `VIDEO_ACCEPTANCE.json` 为准，合集和清单 SHA 由实际交付记录
给出。最终清单包含原图 179 张（原生124、成功配对14、历史失败配对4、相机21、
响应7、额外对照9），另有视频代表帧251与副本抽查8；历史 RUN1/2/3 不重复计入。
最终独立视觉报告 SHA256：`798269c2e7720a5431ce951933c63361bcc59de2f691b40250865315c1eaa2b6`。

resume03 停服与 `verify_cleanup_final` 均 rc0。`service_shutdown_resume03.json`
三服务 remaining_owned_processes 均为空；`shutdown_gpu_ports_resume03.json` 记录
8000/8750/8780 关闭；`owned_process_verification_final.json` passed=true 且
live_owned_identities=[]。ZIP/原件本地双核验以随附 `LOCAL_VERIFICATION`、
`VIDEO_FILES.json` 和封包后生成的 `DELIVERY_RESULT.md` 为准。

文档整理：`/root/cloud_code_review`，本轮只读，不改变旧产物或实验状态。
