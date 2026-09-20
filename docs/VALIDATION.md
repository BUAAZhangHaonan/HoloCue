# 验证标准

所有验收使用当前服务器代码和本次新建的运行目录。压缩包中的沙箱证据作为迁移参考，原生验收结果保存到 `runs/simulation/acceptance_*`。每次失败保留原始日志与模型回复，修复后另建目录重跑。

## 验收内容

| 验收层 | 必须保存的内容 |
|---|---|
| 自动测试 | pytest 输出、XML、依赖版本、代码摘要 |
| 真实模型 | 十二场景的完整有序步骤、背景提示、暂停、中断、显式完成、恢复和实体位姿；原始请求与回复 |
| Viser | 真实按钮与输入框、宽屏与较窄窗口、每个操作对象的特写与检查面、焦点与亮度像素变化、页面错误、视频 |
| Blender | 十二份 scene.blend 和原生图像；同会话起点、过程、终点、临时检查、恢复与完成帧；相机、对象、Gaussian 数值核对 |
| 并发与故障 | 两个客户端隔离、快速消息、在途取消、API 重启、过期包拒绝、模型连接失败与显式恢复 |
| 独立审查 | 三个新建独立 SubAgent 会话的视觉、状态任务、架构安全报告；相同最终代码摘要和实际证据摘要 |

几何检查按完整任务顺序覆盖十一条插入或放置路径及七条旋转路径，后续路径使用前序明确完成后的实体位姿。同一对象旋转与随后的检查保持独立步骤。每条路径采样 41 个时刻，每个移动对象采样 1536 个表面点，随机种子为 4701，穿入阈值为 0.75 毫米。报告保留步骤身份、角度、前序完成记录、实体位姿、采样面索引和全部命中；不能把安装部位的体积重叠直接豁免。该检查仅代表这些采样时刻与表面点，仍需查看原生动画。

碰撞检查对实际 glTF 网格的独立副本合并重复顶点并清除退化三角面，随后检查闭合性与面方向；不填补孔洞，也不改写资产。报告逐个列出障碍部件的原始拓扑、规范化后的拓扑和覆盖状态。只有明确的文字标签平面排除在实体障碍之外；任何其他未闭合实体或穿透采样都会使检查失败，不能把未检查的障碍计入零穿透结论。

## 4029 运行环境

先设置 README 中的项目内部临时目录与缓存，加载本次保存的 `.work/task_env.sh`。模型使用物理 GPU 1；同会话 Blender Cycles 使用物理 GPU 2，资源守卫将物理编号映射为 UUID。应用、Chromium 与 VTK 使用软件渲染。Blender 保留 48 个采样，桥接透明反弹上限为 1024，Gaussian 透明度使用浮点属性。

桥接使用原生 Cycles 渲染与原生合成器。每个提示层最多包含 768 个完整 Gaussian 平面，保留全部点和原始顶点、半径、浮点透明度及颜色；实际场景以 holdout 保留遮挡。同色段中，共面且屏幕矩形重叠的平面分配到不同原生渲染层；没有共面冲突的段采用深度交错分组。分组只改变渲染批次，不改变几何。同色透明层的 AlphaOver 可交换，不同颜色段仍保持从远到近的顺序。提示层最少透明反弹为 768，关闭仅作用于颜色的去噪，基础场景保持原有设置。每次保存各层线性 32 位 EXR、成员清单与摘要。合成器每批最多加载 16 个提示层与 1 个累积图层，保存线性中间结果并释放图像，再继续下一批；最终 PNG 仅应用一次显示变换。不能使用曾出现黑块或灰边界的诊断图像作为通过证据。

VTK 显式创建 `vtkOSOpenGLRenderWindow`，运行时检查必须为 `llvmpipe` 或 `softpipe`。4029 的 OSMesa 安装在项目 `.work/osmesa`，不修改系统库。其 Ubuntu 22.04 软件包来源与摘要为：

```text
https://security.ubuntu.com/ubuntu/pool/main/m/mesa/libosmesa6_23.2.1-1ubuntu3.1~22.04.4_amd64.deb
SHA256 d961bee304d032b7a3f626239366bbe36c4481adb5699813389cdbd08d682269
```

在已设置项目缓存后，用 `curl -fL` 下载到 `.work/packages`，核对摘要，再以 `dpkg-deb -x` 解包至 `.work/osmesa`。在其 `usr/lib/x86_64-linux-gnu` 内建立 `libOSMesa.so -> libOSMesa.so.8`。将此目录加入 `LD_LIBRARY_PATH`。现场 Anaconda 的 C++ 库较旧，VTK 命令单独预加载已有 `/lib/x86_64-linux-gnu/libstdc++.so.6`。设置方式依据 [VTK 官方运行时文档](https://docs.vtk.org/en/v9.6.1/advanced/runtime_settings.html)。

## 执行命令

以下命令在项目根目录执行，先 `source .work/task_env.sh`。所有长进程由 `scripts/guard/resource_guard.py` 包裹；应用与测试上限 8 GiB，原生渲染进程树上限 12 GiB，模型上限 32 GiB，主机预留至少 32 GiB 和总内存 20% 中的较大值。

```bash
"$APP_PYTHON" -m pytest --basetemp=.work/pytest --junitxml=runs/simulation/domain_tests.xml
"$APP_PYTHON" scripts/scenes/check_scene_kit.py --require-blender
"$APP_PYTHON" scripts/tests/audit_geometry.py
LD_PRELOAD=/lib/x86_64-linux-gnu/libstdc++.so.6 "$APP_PYTHON" scripts/scenes/run_visual_batch.py
"$APP_PYTHON" scripts/scenes/build_evidence_gallery.py
"$APP_PYTHON" scripts/tests/independent_check.py
"$APP_PYTHON" scripts/tests/live_twelve_scenes.py --out "$RUN_DIR/live"
"$APP_PYTHON" -m scripts.tests.audit_viewer_live --out "$RUN_DIR/browser"
"$APP_PYTHON" -m scripts.tests.audit_response_live --out "$RUN_DIR/response"
"$APP_PYTHON" -m scripts.tests.audit_bridge_live --out "$RUN_DIR/bridge"
"$APP_PYTHON" -m scripts.tests.audit_resilience_live --out "$RUN_DIR/resilience"
```

故障验收需要其他会话、导出器与桥接停止使用 API 后单独执行。先加载 `.work/task_env.sh`，在独立资源守卫下运行 `"$APP_PYTHON" -m scripts.tests.audit_resilience_live --faults --api-service <当前本次记录的API服务名> --out "$RUN_DIR/resilience_faults_<新的目录名>"`。模型连接失败使用本机绑定但未监听的独占端口产生真实连接拒绝；必须同时记录页面错误、任务错误与停止的动作时钟。恢复真实模型连接后仍须由页面显式发送指令，真实模型成功回复才算恢复验证通过。

脚本在 `finally` 中按拥有记录停止自己新建的全部 API，报告 `test_owned_api_stopped=true`、`current_owned_api_service=null` 和 `external_api_restart_required=true`。这些 API 属于审计资源守卫的后代，不能在守卫结束后继续保留。主线程须等审计进程及其外层守卫退出，检查报告，再从该守卫之外执行 `"$APP_PYTHON" .work/launch_owned.py <新的独立API服务名> -- bash scripts/run_simulation.sh api`，保存新的进程记录并检查 `/health`。所有服务名称必须唯一；停止服务必须核对记录中的 PID、创建时间、项目目录和 API 启动命令，只清理本任务拥有的进程树。脚本不会停止真实模型服务或其他项目服务。

同会话逐阶段验收通过界面中“动作播放速度”设置为 0.1 倍速，为软件渲染下真实暂停按钮的响应留出时间，记录动作中间状态；不修改动作角度、路径或约定时长。N 与 σ 的响应验收由真实模型解释优先级与显示需求，在相同暂停状态、相机、焦点与亮度下比较实际三维画布，不将参数面板文字计入像素差。

原生桥接在每次手动选择视角后，实际点击“聚焦选中对象”，按场景契约中的提示点或检查面核对相机深度与导出的焦距，并保存 `focus_actions.json`。手动视角切换本身保留用户焦距，因此不能把此前视角的焦距当成新检查面的聚焦结果。聚焦通过真实控件执行，不直接写入视图文件或修改解析参数；两端随后消费同一份相机与提示数组。专门的亮度和离焦响应验收仍使用各自已记录的固定相机与控件操作。

带有接收对象的移动动作使用工作区域视角保存恢复、过程与终点，避免源对象特写裁掉远处接收槽。到达终点并保持暂停后，另拍接收对象特写，同时断言观察切换前后的任务状态完全一致；完整十二场景因此增加十一组接收对象画面。恢复结构检查时选择原对象的检查面。每个对象的普通特写与结构检查画面仍单独保留，视角切换不能代替明确完成动作。

服务器发布视图状态不等于浏览器已完成绘制。桥接在原生渲染前保留一张真实页面截图，原生渲染后继续截图，核对任务时钟、版本、相机、焦距与亮度始终不变，并要求连续两张画布像素及渲染尺寸完全一致。最多记录六张，未稳定则明确失败；所有早期截图保留，`viser.png` 是最后一张实际稳定截图的原文件副本，`browser_capture.json` 保存时间、画布尺寸、设备像素比和摘要。该检查证明采集时画布稳定，不替代提示可读性与资产视觉审查，也不声称是客户端消息确认协议。

原生图像属于离线证据。较宽的提示可能使数千个共面 Gaussian 平面互相重叠，在保持全部几何、浮点透明度和 48 次采样时需要上千个原生层。每帧总等待上限为 90 分钟，连续 5 分钟没有渲染日志进展则失败；`native_wait_policy.json` 保存限额与实际等待时长。该限额只控制离线执行时间，不改变图像、数值核对或资源守卫，也不构成实时帧率证明。超时和不完整层集不能计为通过。

## 审查与归档

`scripts/release/check_review_gate.py --digest` 计算代码、配置、资产和文档摘要。三个最终审查分别使用 `scene_visual`、`state_tasks`、`architecture_safety` 范围，保存独立会话标识、原始输出、实际命令、证据路径和 SHA256。视觉审查明确列出看过的图像与视频。代码变化后重做受影响的实测，并让三份审查对应最终摘要。

`independent_check.py` 是独立进程检查，不能替代 SubAgent 审查。最终报告区分解析提示响应、真实模型交互与原生渲染，不将这些结果表述为物理全息实验。

使用独立验收目录时，给该脚本传入 `--rendered <本轮VTK图像目录>`、`--geometry <本轮几何报告>`、`--junit <本轮pytest XML>` 和 `--out <本轮独立进程报告>`。直接读取 `validate_renderings.py` 的平铺图像目录时加 `--flat-rendered`；`run_visual_batch.py` 的场景子目录采用默认布局。报告记录实际读取的输入路径和布局，避免误用默认目录中的历史结果。
