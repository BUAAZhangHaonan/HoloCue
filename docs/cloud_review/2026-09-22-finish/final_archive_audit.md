# 最终封存 ZIP 独立审计

**通过，未发现实际阻碍。** 审查会话 `/root/cloud_provenance_review` 于 `2026-09-21T19:09:01.300019Z` 独立读取服务器实际封存 ZIP，重新计算包 SHA256、每成员 CRC32/SHA256/大小及精确集合；未使用主线程的 passed 标记代替核验，未解压、修改封存材料或运行实验。

73 个 ZIP，9,575 个项目成员及 6 个索引成员，共 9,581。总大小 **1,856,724,996 字节**；最大 **48,036,517 字节（45.8112 MiB）**，全部严格小于 48 MiB。与 UPLOAD_INDEX、SHA256SUMS、包内 MANIFEST 完全一致；无缺失、额外、重复或不安全成员路径。

## 来源与实际范围

- 最终源码摘要：`d8d73e7d849b949bfee3827d6f60dfb86351cc50b49f98027b92db1664392806`。两阶段快照均独立重算摘要，新旧唯一源码差异为 viewer_scene.py，旧源码精确副本仍在包内。
- 121 条 RUN4 执行记录各自源码前后稳定、资产不变。101 条属于 c33 历史阶段，20 条属于 d8；STATUS/COVERAGE 与原始 execution 的身份和返回码一致。
- d8 当前检查为最终 pytest **529 通过、0 失败/错误/跳过**，实际相机 **10 轮通过**及 Shelf attempt03 通过。旧 c33 pytest/live/response 与 12 场视频维持历史阶段身份，没有冒称在 d8 重跑。
- 八个原始完整 native 目标在各自已记录阶段具有通过证据；四个 focus 结果保留历史 scope。包级完整性不将这些不同阶段升级为 d8 全场 native 验收。旧资源中断、视觉拒绝和预检拒绝记录均保留。
- 资产摘要 `36866cf33627a522897a66a3e1247587608d72959dc792d029de0136a0b78af8` 独立重算一致：**76 个场景 GLB + 27 个 fixture = 103 项**，逐项与包内实际字节一致。三个新构建 blend 与早先独立记录的哈希一致，其余历史来源不升级。
- RUN2 封存继承的 2,005 项及 RUN3 冻结 inventory 的 1,072 项逐项与包内哈希/大小一致。

## 图像、模型回复和视频

visual_review_seal 列明的 10 个报告/manifest 哈希与封存前预核一致；VIDEO_ACCEPTANCE 与创建命令所载哈希一致。五张诊断原图副本与冻结 final_review_inventory 及原图三方哈希相符，没有修改旧视觉报告，也没有计作新抽帧或 native 图。

179 张已审原图、251 张代表性视频抽帧和 8 张副本清晰度抽帧的来源界限保留。RUN4 包内共有 1,282 个 PNG、102 个 MP4/WebM 文件；这些是文件计数，包含辅助、片段和失败材料，不等于全数人工观看或 102 个完整演示。

12 个显式接受 production 与旧拒绝 connector production 的 session、c33 来源和媒体哈希一致。其 events/api_reads 均入包，每个 production 保留两次 HTTP 200 的 raw_http_body/raw_response，共核对 26 条原始回复记录；未将功能通过覆盖视觉拒绝。

8 个大原件通过明确替代关系保留完整本地交付身份，ZIP 中选入其审阅副本。包内副本哈希/大小、完整解码帧文件及各验证证据哈希、三条实际 rc0 执行、原分辨率/fps/帧数及逐帧相对 PTS 相符；8 项最大相对 PTS 误差均为 0。原件不在 ZIP 中，包内 local_video_inventory 的原件大小/SHA/Windows 路径与替代证明一致。该 SHA 同此前独立读取的远端原件一致；按主线程要求，本审计不重复其已全量完成的 Windows 媒体哈希检查。

隔离 Viser runtime 构建保持 `db213945693b3efd036c6d2c6c27eca2147ea7648a95938d3a8fcd218a15be2f`，与 application source 分开。停服/进程退出/端口证据及三份 local_delivery_logs 均在包内。

## 审计文件与边界

- 实际封存包：`/home/hdd3/zhanghaonan/projects/holocue/runs/simulation/cloud_finish90_20260921_e67b574/upload/`
- 远端补录：`/home/hdd3/zhanghaonan/projects/holocue/.work/cloud_finish90_20260921/final_archive_audit.md`、同目录 `final_archive_audit.json`
- 本地补录：`E:/OneDrive/文档/Playground/.work/holocue/cloud_finish90_20260921/final_archive_audit.md`、同目录 `final_archive_audit.json`
- 独立程序：同目录 `final_archive_audit.py`；SHA256 `22330647b3ebdabcae2ad7a00cf1add47157dadf2fc6754d14cbd133baa3607c`。
- JSON SHA256：`9b1477bfc1f3b3294c8ccbc46ee0a3645fb998e452cec818af5e1cd199dcf587`，包含全部包/成员实际哈希与逐项语义核验结果。
- UPLOAD_INDEX SHA256：`4029bb4b9ae4fab43af076cf81982995cb68264d935818525cab3f37e1ced806`；SHA256SUMS SHA256：`908c96c46fb76572b48e1b1c88cf8b513635b2dbc35b18a912c0432cf956249f`。

这是封存后的独立补录，不回写 ZIP 或其内部入选报告。包内较早报告所写“ZIP 待验”保留其当时事实；本补录完成这一包级核验，不新增实验结论。