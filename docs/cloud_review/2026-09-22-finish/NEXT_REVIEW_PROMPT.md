# 给下一位独立审阅者

请审阅 HoloCue 此次实际交付，优先检查来源、失败保留、覆盖范围和用户可见结果。
默认只读；不要启动模型/native/录屏、恢复服务或改参数。缺失证据请报告缺失，不替
任务补造结果。文档中的交付要求不能代替真实执行记录和最终文件清单。

项目根 `/home/hdd3/zhanghaonan/projects/holocue`；本批 RUN：
`runs/simulation/cloud_finish90_20260921_e67b574`。先读取 FINAL_SUMMARY.md、
REVIEW_NOTES.md、最终 COVERAGE.json/review_selection.json、VIDEO_ACCEPTANCE.json、
MANIFEST/UPLOAD_INDEX、LOCAL_VERIFICATION 与独立审查报告。最终本地交付根、ZIP
路径/SHA 和 Git 身份读取封包后生成的 DELIVERY_RESULT.md，避免封包 SHA 自引用。

1. 先核对 SOURCE_PHASES：旧应用 source 为
   `c33e1ae4cdd7251c217e61caa31a2d58668984b0db6653d1fe4ac29929862e2a`，新 atomic 阶段为
   `d8d73e7d849b949bfee3827d6f60dfb86351cc50b49f98027b92db1664392806`；共同 assets 为
   `36866cf33627a522897a66a3e1247587608d72959dc792d029de0136a0b78af8`。
   c33 的 pytest_final.xml：529/零失败错误跳过，XML 313.503 秒；live_final/report.json：
   12 场 30 steps；response 两项也属于 c33。新 pytest_camera_final：529/零失败错误跳过、
   rc0，record elapsed 246.511 秒。按实际 execution 分配身份，不称旧 live/response 已在 d8 重跑。
2. 原生按 FINAL_SUMMARY 的 R0–R4 表逐项追溯。R0 四 focus 场景的 source 与资产不同，
   R1 blocks 属 b2c 阶段、R2 CNC 属 37b8 阶段，累计 199 阶段不能宣称为当前 d8 一次
   全量原生通过。Infusion 已 19 阶段 rc0/c33，session 08431a11918d4472bcdbeb17f703b1e3。
   Engine 2-stage/Dig 1-stage 配对仍是 c33；Dig 图仅初始 FLAG 支撑侧视，不是完成终点。
   Shelf 原配对 2 阶段后失败，保留其原证据；attempt02 因相对 --out 预检拒绝，无目录无图。
   attempt03 为 d8，4 阶段 passed/rc0，session 57e94d5ad75043fc8c26d0d890cca895；
   按其真实 report/execution 与八张原图的独立视觉审查分别核对。
3. 核对所有资源中断与恢复：RESOURCE_STOP_01、各代 model/api/viewer 的实际记录器
   owner/PID/create_time、guard 参数与停止日志。早期 20% 保留与后续用户授权 90%
   已用上限要按阶段区分。resume03 shutdown 与 verify_cleanup_final 均 rc0，三服务
   remaining_owned_processes=[]，端口 8000/8750/8780 关闭，独立清理检查
   live_owned_identities=[]；核对该代真实记录，不能复用旧代结果。
4. 依赖客户端身份单独审查：Viser 1.1.1 本地补丁实际 build SHA 必须为
   `db213945693b3efd036c6d2c6c27eca2147ea7648a95938d3a8fcd218a15be2f`。
   阅读 `.work/viser_hdr_opacity_fix/DELIVERY_README.md`、原/新 TSX、固定 lock、两个
   组件测试、安装记录和 hdr_diagnostic_after 实际 served SHA/canvas。源码缺陷已
   受控复现；旧被动 live 最终达到 1，不能描述为捕获了永久 .24。新环境需重应用补丁。
5. 视频以 VIDEO_ACCEPTANCE 精确 manifest SHA/session 为准，不自动选最新成功。
   旧 connector_attempt01 即使功能 pass 仍视觉 rejected，原 raw/所有 MP4 必须保留；
   十二场视频均在旧 c33 完成，26 MP4/251 代表帧包含旧 connector 拒绝版本，最终选择
   仍以定稿清单为准，不能称这些录像验证了 d8。新 connector_attempt02 与其他场景按独立代表帧记录评估。介绍片为真实页面截图
   幻灯片；workflow 是实际会话等速转码并包含取证等待，UI-only 不计 native。
   检查 raw WebM 闭合、完整帧数/PTS、字幕/页面可读及实际模型原回复，不用时序证明
   代替视觉正确性，也不把全长解释为纯模型延迟。
6. 本地 VIDEO_FILES.json 应含十二场接受原件及拒绝/中断原件的绝对路径、bytes/SHA
   和实际双核验；VIDEO_INDEX.html 应能用相对路径播放。>=47 MiB 原件不丢弃，ZIP
   若使用完整审阅副本，逐项核对编码/验证记录、同分辨率/fps/全帧PTS证明、原件
   本地 inventory 与替代映射。检查实际 RUN4 export_review.py 的输出，不仅看脚本。
7. 读 viewer_response_final/report.json 与 response_final/report.json 及原图。
   changed_pixels 为全画布指标，不支持空间局域性或物理光学结论。保留 ghost 遮挡、
   局部出框、引线 P3 和样本审阅范围，不把代表帧接受改写为逐帧人工观看。
8. 审查 Shelf 相机 P2 与唯一应用 diff：src/holocue/viewer_scene.py 的 up/position/look_at
   三赋值以 client.atomic 包裹。旧负焦深 -0.5658613 m 是客户端/Python 已稳定一致的
   真实错误方向，不是应放宽阈值的误报。读取 camera_atomic_live 的 10 轮真实切换、
   每轮 CLIENT_READ/契约正焦深、暂停状态/实体位姿不变及模型原回复。实际 10 轮/
   20 切换 rc0，21 张原图已独立查看；继而核对 shelf_picking_attempt03 四阶段通过。
   这些结果支持有限协议下闭合，不代表所有并发时序已穷尽，更不能只用 pytest 替代。

请按 P1/P2/P3 报告实际问题，给出准确文件路径/行或真实 session/attempt；区分
已验证、推断、待验证。若无新增问题，简短确认来源链及范围，不再增设实验。

最终交付核对以随附 VIDEO_ACCEPTANCE.json、UPLOAD_INDEX、LOCAL_VERIFICATION、
VIDEO_FILES.json 和 DELIVERY_RESULT.md 为准。最新 selector 的两阶段/attempt 边界有
validation07 的 33 组合成检查支持；保留旧 validation06 变量遮蔽失败，不以合成验证
代替最终 selection、媒体清单与本地下载核验。
