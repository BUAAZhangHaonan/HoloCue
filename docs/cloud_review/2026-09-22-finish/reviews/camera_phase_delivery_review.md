# 两阶段交付边界独立复核

审查者：`/root/cloud_code_review`。本报告整理刚完成的只读局部复核，不新增执行或修改工具；旧 `delivery_helpers_cross_review.md` 保持原字节。

本地工具目录：`E:/OneDrive/文档/Playground/.work/holocue/cloud_finish90_20260921/`。对应服务器目录为 `/home/hdd3/zhanghaonan/projects/holocue/.work/cloud_finish90_20260921/`。

| 已读取工具 | 实际本地 SHA256 |
| --- | --- |
| `prepare_delivery.py` | `8a5d1cfe048f8479a35cfe7124ba1854f24f2c67b315cd338194d740604a1592` |
| `download_videos.py` | `9ede5f88036805382c6463e5e3167e4d3883a5737e25564f551c1e3e6e8d3c0a` |
| `combine_introductions.py` | `e9461f567bfe414db4b61daeefb69e3f4a86a095ffa394e124162e11e579c6b5` |

本次边界为 RUN `runs/simulation/cloud_finish90_20260921_e67b574` 内的 `SOURCE_PHASES.json`：旧 source `c33e1ae4cdd7251c217e61caa31a2d58668984b0db6653d1fe4ac29929862e2a`，相机 atomic 修正后 source `d8d73e7d849b949bfee3827d6f60dfb86351cc50b49f98027b92db1664392806`，共同 assets `36866cf33627a522897a66a3e1247587608d72959dc792d029de0136a0b78af8`。

局部检查结论：**未发现新增实际缺陷**。

- 三工具读取显式两阶段清单并校验快照文件 hash、阶段标识、唯一变化路径 `src/holocue/viewer_scene.py` 和保存的旧文件身份。选择器另将当前源码完整快照与实际项目比较（`prepare_delivery.py:194–239,328–337`）。
- 每个命令必须已结束，source 前后稳定且属于声明阶段，assets 前后保持同一身份。旧 c33 命令保留 historical，最终 d8 命令为 current；原 pytest/live/response 与新 camera 检查分栏，未把历史结果改写为新源码执行（`prepare_delivery.py:409–417,579–591,1144–1190`）。
- 十二场已接受视频仍绑定旧 c33 capture/produce；合集分别记录输入媒体 source 与其实际制作命令的 execution source，不把新阶段合成操作解释为重新采集十二场视频（`prepare_delivery.py:762–805,822–865`、`download_videos.py:260,334–349`、`combine_introductions.py:127–140,169–196,227–231`）。
- Shelf 新 helper 的 `--out` 从真实命令解析；输出必须属于本 RUN `changed_pairs` 且 owner 唯一。旧失败与新 attempt 独立保留，按 report 自身 scene 匹配；“曾在某阶段通过”和“最终源码通过”明确分开（`prepare_delivery.py:243–261,1081–1105`）。

验证范围仅为上述源码边界及三份本地文件 SHA。没有重新执行实验、测试、最终 selection、打包或 download；没有检验最终实际文件集合与本地媒体下载完整性。这些需要以主线程后续真实执行记录为准。先前合成验证记录也不替代最终产物验收。
