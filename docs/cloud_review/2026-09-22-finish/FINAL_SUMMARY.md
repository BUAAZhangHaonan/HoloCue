# HoloCue 本批交付总结

日期：2026-09-22。

c33 阶段已完成
529 项测试、十二场景 30 步 live、两项页面响应检查及十二场视频；原生按历史来源
累计通过 199 阶段。随后 Shelf 定向配对暴露真实相机 P2，最小 atomic 修正形成
d8 新阶段，其 529 项测试、10 轮真实相机回归和 Shelf attempt03 四阶段配对已通过，
resume03 已停止并独立核验清理。不能将 c33 的运行结果改写为 d8 已执行。
最终媒体选择、封包、下载及 Git 身份以随附交付清单和封包后生成的 DELIVERY_RESULT.md 为准。

所有下述路径均相对于服务器项目根
`/home/hdd3/zhanghaonan/projects/holocue`。本批 RUN（下称 R4）为
`runs/simulation/cloud_finish90_20260921_e67b574`。其他来源：

- R0：`runs/simulation/repair_review_20260920_25bcc909`
- R1：`runs/simulation/cloud_update_20260921_ce64aff5`
- R2：`runs/simulation/cloud_resume_20260921_ea8c2f7`
- R3：`runs/simulation/cloud_continue90_20260921_6815e62`

## 从 Repair Review Kit 开始的实际实现交付

本交付延续最初的定向修复，不仅是 R4 的续跑。三处文件读取已经替换：
`tests/test_engine_clamp.py` 通过 `src/holocue/glb_attributes.py` 使用 Trimesh
公共 GLB 接口读取实际存储法线；`tests/test_asset_normals.py` 的几何数组交给
Trimesh、材质/纹理元数据交给 pygltflib；`scripts/ops/validate_model_dir.py` 使用
官方 Safetensors `safe_open` 惰性检查键名、shape 与分片索引。R0 记录了真实模型
两个分片、738 个张量的目录验证。后续 Cloud Update 另补官方 Khronos glTF Validator
严格格式检查，将 GLB 尾随数据按错误处理并保留禁止 sparse 的公开元数据约束；
不能将 R0 当时仍缺少的格式边界断言倒写为早已完成。

既有 CLAMP 金属座与软管通道、L1/L2 缩短支柱及真实盲座实现被保留，R0 的
`modeling.py` 与 22 份原 fixture 未因读取器替换而改写；原有几何、材质、法线、
尺寸和接触回归继续检查。R0 `COVERAGE.json`/`pytest_results.xml` 记录完整
431 项通过，其中联合几何回归 89 项；`geometry.json` 的十八条有序动作保持
1536 点、seed 4701、41 时刻和 0.75 mm 阈值。后续 Cloud Update 对指定箱体与
软管材料分区作连续表面修复，不能把这次实际资产变更混称为 R0 原件未改。

Optical M 使用官方 `environment_wxyz` 固定环境方向
`[0.594394087626887, 0.1712372678360988, -0.2126979877009283, 0.7563947598484568]`，
保持 studio、强度 0.1、金属度 0.95、粗糙度 0.08；其他场景方向不变。R0 `mirror/`
保存真实会话初始/顺时针 15°完成状态的调整前后配对、相机/材质/环境记录，独立
视觉确认镜面和边框可辨，初始右侧暗带仍作为实际反射保留，不声称物理光学标定。
标准 `scripts/scenes/build_all.sh` 已统一为 GLB→payload→Blender，分开记录请求
范围、实际 built 范围与全盘 inventory；R0 实际生成 76 个 GLB、十二份 payload、
十二份 `.blend` 和十二张原生全景，逐份关联输入/源码/资产/输出哈希，并由
`build_verification.json` 核对。来源为 R0 `assets.provenance.json`、
`build_provenance/*.json`、`build_command/execution.json`、
`build_verification_command/execution.json`、`mirror_command/execution.json`。

上述 R0 验证的原执行身份是 source
`2ef99b6626387225afacc10502e6d3b83e1359a0c7e528d7036e54f683002366`、asset
`1926ec8e7f696dd3565ce016f144f640c630c6d305441062921c5e18efc1280d`，并由 R0
`COVERAGE.json` 和三份独立审查记录限定覆盖。其后的边缘标签/对象说明、材料分区、
严格 GLB 格式、异步相机验收与客户端透明度修复，以及当前测试、原生续跑和 UI 视频，
按下文各阶段身份接续交付；不将历史构建和回归改写成后续 c33/d8 的重新执行结果。

## 当前身份与已完成检查

本 RUN 的 SOURCE_PHASES 必须保留两个独立来源：旧阶段 source digest 为
`c33e1ae4cdd7251c217e61caa31a2d58668984b0db6653d1fe4ac29929862e2a`；
当前 camera atomic 阶段 source digest 为
`d8d73e7d849b949bfee3827d6f60dfb86351cc50b49f98027b92db1664392806`。
两者唯一应用代码差异是 `viewer_scene.py` 把 up/position/look_at 三赋值包入
`with self.client.atomic():`，没有改模型、几何、焦点阈值或采样协议。
当前 asset digest：
`36866cf33627a522897a66a3e1247587608d72959dc792d029de0136a0b78af8`。
Viser 1.1.1 本地客户端补丁不在该应用摘要内，必须另记录实际 build：
`db213945693b3efd036c6d2c6c27eca2147ea7648a95938d3a8fcd218a15be2f`。
最终 Git HEAD/工作区状态以随附 `DELIVERY_RESULT.md` 的实际记录为准。

| 检查 | 已核结果 | 精确证据路径（R4 内） |
| --- | --- | --- |
| pytest（c33 历史阶段） | 529 passed，0 failed/error/skipped，XML 313.503 秒，命令 rc0 | `pytest_final.xml`、`pytest_final_command/execution.json` |
| 十二场 live（c33） | 12 场全部 passed，共 30 steps，backend_mode=live，rc0 | `live_final/report.json`、`live_final_command/execution.json` |
| Optical 页面响应（c33） | passed，brightness changed_pixels=2585，focus=312，browser_errors=[] | `viewer_response_final/report.json`、`viewer_response_final_command/execution.json` |
| Control 显示参数响应（c33） | passed，N high→low=76050、low→sigma_wide=351288 changed_pixels，browser_errors=[] | `response_final/report.json`、`response_final_command/execution.json` |
| pytest_camera_final（d8 新阶段） | 529 passed，0 failed/error/skipped，rc0；record elapsed 246.511 秒 | `pytest_camera_final_command/execution.json`；XML 路径按该记录 command 核对 |
| 相机定向回归（d8） | 10 轮、20 次 BLUE inspection→BASKET detail 切换，rc0；21 张原图已独立查看 | `camera_atomic_live/result.json`、`camera_atomic_live_command/execution.json` |

前四项执行记录的 source/assets 前后均匹配 c33/3686；后两项为新 d8/3686。旧 live 和
response 没有因此在 d8 重跑，不能称新源码全量运行通过。页面像素差异是整画布响应
证据，不证明空间局域性、真实光学焦深、物理亮度或标定精度。Control 检查通过已有
可见设置选择 Device Pixel Ratio=1.0，产品默认仍为 Adaptive。旧 R1 的 519 测试
属于 b2c379ba… 阶段，保留原身份，不替代或改写为本次 529。

## 原生证据按来源继承

表中“通过阶段”指对应 report 的 stages 数量；每项均应连同同 RUN 的命令
execution.json 阅读。不同历史源码与资产不能合并为一次最终源码全量原生通过。

| 场景 | 已核状态/阶段数 | report 与命令（相应 RUN 内） | source 摘要前缀 |
| --- | --- | --- | --- |
| blocks | passed / 13 | R1 `bridge_batches/blocks_final/report.json`；`bridge_blocks_final_command/execution.json` | b2c379ba |
| cnc_toolchange | passed / 18 | R2 `bridge_batches/cnc_toolchange/report.json`；`bridge_cnc_toolchange_command/execution.json` | 37b81f92 |
| connector | passed / 14 | R3 `bridge_batches/connector/report.json`；`bridge_connector_command/execution.json` | c33e1ae4 |
| control_panel | passed / 11 | R3 `bridge_batches/control_panel/report.json`；`bridge_control_panel_command/execution.json` | c33e1ae4 |
| dig_site | passed / 18 | R3 `bridge_batches/dig_site/report.json`；`bridge_dig_site_command/execution.json` | c33e1ae4 |
| dive_fillstation | passed / 23 | R4 `bridge_batches/dive_fillstation/report.json`；`bridge_dive_fillstation_command/execution.json` | c33e1ae4 |
| drone_bench | attempt02 passed / 20 | R4 `bridge_batches/drone_bench_attempt02/report.json`；`bridge_drone_bench_attempt02_command/execution.json` | c33e1ae4 |
| infusion_ward | passed / 19，rc0；session `08431a11918d4472bcdbeb17f703b1e3` | R4 `bridge_batches/infusion_ward/report.json`；`bridge_infusion_ward_command/execution.json` | c33e1ae4 |
| engine_bay | 历史 focus passed / 18 | R0 `bridge/report.json`；`bridge_command/execution.json` | 2ef99b66 |
| optical_bench | 历史 focus passed / 17 | 同上 | 2ef99b66 |
| server_rack | 历史 focus passed / 14 | 同上 | 2ef99b66 |
| shelf_picking | 历史 focus passed / 14 | 同上 | 2ef99b66 |

R0 四场资产摘要为
`1926ec8e7f696dd3565ce016f144f640c630c6d305441062921c5e18efc1280d`，
与当前资产不同。其余表中已完成原生使用当前 36866cf… 资产。表中累计 199 阶段
是分阶段来源的已通过记录，不能称同一最终源码、尤其新 d8 下 199 阶段全量通过。
修改部位另由定向配对补充：R4 `changed_pairs/engine_bay/report.json` 为 2 阶段、
`changed_pairs/dig_site/report.json` 为 1 阶段，对应 `pairs_engine_bay_command/`
和 `pairs_dig_site_command/execution.json` 均 rc0，仍为 c33/3686。Dig 图是初始 FLAG
支撑侧视，**不是任务完成后的终点图**。Shelf 原配对在 2 阶段后失败，不能算完整
通过。attempt02 仅因主线程使用相对 `--out` 被 helper 预检拒绝，无输出目录、无图，
不构成第二次相机行为失败。实际重跑为 `changed_pairs/shelf_picking_attempt03/report.json`，
4 阶段 passed，`pairs_shelf_picking_attempt03_command/execution.json` rc0，source d8/3686，
session `57e94d5ad75043fc8c26d0d890cca895`。其八张原图的最终视觉结论以随附独立视觉
审查记录为准，不以程序 passed 代替人工图像判断。

Shelf 原 `changed_pairs/shelf_picking/focus_failure.json` 保存负焦深
`-0.5658613019468908 m`；实际客户端/Python 相机已稳定一致，但目标位于相机后方，
聚焦按钮服务端亦抛异常。这是实际相机 P2，不是放宽容差可以解决的验收误差。
唯一应用修正是前述 atomic 三赋值；原失败、截图及模型回复保留。
`camera_atomic_live/result.json` 与对应 execution 记录 10 轮、20 次真实切换通过，
保持原严格正焦深/契约一致、暂停状态及实体位姿检查，rc0；21 张原图已实际独立查看。
与 Shelf attempt03 一起，这些结果支持本次有限切换协议下的修复闭合，不证明所有
并发时序均已穷尽，也不覆盖 d8 下十二场完整原生重跑。

## 视频与本地客户端修复

每场演示是独立真实 Viser UI 会话；保留原模型回复、暂停、检查、恢复、确认及
原始 WebM。它们属于 UI-only，不替代 Blender/native。演示 MP4 对实际录像等速
转码、无剪切；录制时沿用原 workflow 动作播放倍率 0.1。“等速”指转码不加速，
不表示场景动作倍率为 1.0。录像含截图稳定及取证等待，不能用全长衡量人工操作
耗时或模型纯推理延迟。介绍片是实拍页面全景/关键细节截图的幻灯片，中文文本来自
保存的 scene_contract.json，不是连续动作录像。

旧 connector_attempt01 功能断言完成，但整画布漂白，视觉拒绝；原件保留。
修复仅为 Viser HDR 第二次纹理加载分支恢复 canvas opacity=1。旧组件受控回归
复现 .24，修复后 2/2 通过，固定 lock 的隔离生产构建 rc0；安装后的实际页面
served SHA 为上述 db213945…、canvas=1、browser_errors=[]。新 connector_attempt02
代表帧已独立视觉接受；这不改写旧失败，也不代表人工逐帧观看全片。

详细说明：`.work/viser_hdr_opacity_fix/DELIVERY_README.md`；实际安装与运行证据：
R4 `viser_opacity_install.json`、`install_visor_opacity_fix_command/execution.json`、
`hdr_diagnostic_after/diagnostic.json`。该补丁需在重建/重装 Viser 环境后重新核对应用。

十二场视频已全部在 c33 阶段完成；已审 26 个 MP4、251 张代表帧，计数包含旧
connector 拒绝版本，不是 26 个全部接受的成片，更不是 d8 新阶段录制。原件仍保留。
十二场精确接受 manifest/session、拒绝理由以随附 `VIDEO_ACCEPTANCE.json` 为准；
接受清单 SHA256 为 `aee1680f9a37c3cd45129bcc518aa9341ee04ea55a2822f6331915d762b63ef0`。
十二场介绍合集 `videos/all_scenes_introduction/twelve_scenes_introduction.mp4` 已生成，
时长 282 秒，输入和输出均为 7050 帧，制作 rc0；合集 SHA256 为
`9b11bd76d7725e9b2d060bf9a4c8d707f523a1c5ddc55e5c1ec80dce8653415d`。
最终独立视觉报告 SHA256 为 `798269c2e7720a5431ce951933c63361bcc59de2f691b40250865315c1eaa2b6`。
本批查看 179 张唯一来源原图：原生 124、成功配对 14、历史失败配对 4、相机 21、
响应 7、额外对照 9；另有视频代表帧 251 与副本对照 8，合计 438 个不同路径 PNG。
采用的十二场 24 个 MP4 对应 234 个代表帧；旧 Connector 的 2 个 MP4/17 帧明确拒绝。

## 失败保留与交付尾项

焦点异步检查的早期失败、资源守卫中断、Drone 首次失败、Engine 首次连接失败、
CNC 首次制作中止、旧 connector 视觉拒绝及 Shelf 原配对相机 P2 均保留。后续 attempt/generation 不覆盖
其产物。主机已用 90% 上限经用户明确授权；早期阶段的 20% 保留策略保持历史事实，
不回写成当时已用 90%。资源守卫只处理本任务记录的进程归属。

最终 `shutdown_resume03_command/execution.json` rc0，完成于 2026-09-22 02:41:30
（UTC+8）；`service_shutdown_resume03.json` 的 model/api/viewer 均记录
`remaining_owned_processes=[]`。`shutdown_gpu_ports_resume03.json` 确认 8000/8750/8780
关闭。另 `verify_cleanup_final_command/execution.json` rc0，完成于 02:41:58；
`owned_process_verification_final.json` 为 passed=true、`live_owned_identities=[]`，
按记录 PID/create_time 核对，未处理无关进程。这是本代最终清理，未借用旧代结果。

实际 selection/export/verify、ZIP 列表/大小/SHA 以随附 `UPLOAD_INDEX`、
`LOCAL_VERIFICATION` 为准；本地原件 `VIDEO_FILES.json`、播放索引 `VIDEO_INDEX.html`
的绝对路径和下载 size/SHA 核验由封包后生成的 `DELIVERY_RESULT.md` 汇总。
该文件在封包后生成，避免把最终 ZIP 的 SHA 自引用到 ZIP 内容中。

交付要求是所有原始大媒体完整保存到本地，完成状态以上述下载核验为准。ZIP 对 >=47 MiB 媒体只在存在完整同分辨率、
fps、全帧时序核验副本及本地原件 inventory 时替换，记录原件路径/大小/SHA，不能
静默省略。R2 的 sealed ZIP 链、R3 的冻结 inventory 与 R4 current 证据分开保留。

文档整理：独立代理 `/root/cloud_code_review`；只读现有记录，未新增实验或修改服务器。
