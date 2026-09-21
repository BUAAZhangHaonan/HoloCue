# HoloCue Cloud Update 独立源码审查

- 审查会话真实标识：`/root/cloud_code_review`（当前 collaboration 子代理的 canonical task name；未虚构 UUID）。
- 日期：2026-09-21。
- 范围：4029 `/home/hdd3/zhanghaonan/projects/holocue`，基准 `c4463b3a9842b3945ab7d1582ab8e49fcadca245`，Cloud Update 已合并内容；只读源码审查。
- 本会话未修改服务器、启动服务/模型/渲染、重跑 pytest，也未把云端或历史记录当作本次原生通过。

## 结论与问题

最终限定复审：首轮两项 P2、标签可见性 P2 及 CNC 审计同步补丁均已核对部署字节；最终不同导出稳定要求已在 CNC_final 真实原生流程越过旧T09失败点，整场因API资源守卫停止而未完成。HEAD仍为 `ca213c5d6ea9bd3b9dc7f175cac7aefb7df22ff0`、工作区干净，独立源码摘要 `37b81f92c4bb91b5ca68180be99b1f1810b40657842cf2d3145bd1eeb8d3f0fe`。519项pytest属于此前b2c源码，不能迁移为当前摘要通过。保留客户端断开清理竞态及全部历史失败，不扩大修改范围，不启动新实验。

### 已修复 P2：合法窄视口会抛出布局异常并终止动画线程

位置：`src/holocue/annotations.py:27-29`；调用链 `src/holocue/viewer_scene.py:247-248` → `src/holocue/viewer.py:325-335`；窗口回调 `src/holocue/viewer.py:146-151`。

当前固定 NDC 字高 `.030` 配合最大 ID 长度计算宽度，宽度达到 `.80` 即抛异常。实际 infusion_ward 含 11 字符 `PUMPCASSETTE`，因此 aspect <= `0.03 * (11+2) / 0.80 = 0.4875` 会失败，例如 400×900 的场景视口。`tick()` 每帧直接调用布局，`animate()` 无异常恢复，异常会使该客户端的动画线程退出；随后扩大窗口不会重建该线程。若在初次加载触发，workspace `select_view()` 同样失败。新增布局测试只覆盖 `.75, 1, 1.6, 2.4`，不能排除此问题。

应为有效窄视口确定可计算且保持标签完整的布局/字号策略，并验证缩窄后再扩大不会停止动画。不能仅捕获异常并静默隐藏所有标签来冒充满足窄窗口验收。

实际修复追踪：服务器 `src/holocue/annotations.py:26-29` 已改为 `characters=maxlen+2`、`height=min(.030,.72*aspect/characters)`，再计算 width；去掉合法窄视口的宽度异常分支。对有效正 aspect，宽度至多 .72，正常宽度沿用原字号；这消除了上述触发路径且保留标签。`tests/test_annotation_layout.py:13` 已加入 `.4,.45`。本子代理仅复读代码/参数，没有运行或代报测试和真实窗口通过。

### 已修复 P2：跟随开启时手动选对象，后续同任务快照使侧栏与实际观察对象分离

位置：`src/holocue/viewer.py:113-120` 与 `295-301`。

新下拉回调在用户选择时总会执行 `renderer.select_view(..., self.target.value)`。例如 B 正在旋转，保持“跟随当前步骤”开启，在结构检查中手动选 C：renderer.selected_id 和画面变为 C。随后对仍为同一 task_id 的 B 暂停/恢复，使新快照进入 `accept()`；第296行将下拉恢复成 B，第301行更新侧栏为 B，但第297行因 task_id 未变而跳过 `select_view()`，renderer.selected_id 仍为 C。这会形成 B 的侧栏与 C 的结构检查画面。程序设置下拉产生的事件 client_id 为 None，第118行也不会补做同步。

应在自动跟随改变实际选择时同步 renderer，或为跟随开启时的手动选择定义一致行为。关闭跟随分支目前确实不会由新快照覆盖用户选择；该修复方向是有效的。

实际修复追踪：服务器 `src/holocue/viewer.py:297` 已把重选条件改为 `old_current!=current.task_id or self.renderer.selected_id!=current.target_id`。在原触发序列中即使 task_id 不变，C 与当前 B 的差异仍会执行 `select_view()` 并同步焦点，随后刷新 B 摘要。分支仍受 follow 开关限制，关闭跟随时不会覆盖用户选择。静态复核认为该修复覆盖原问题；没有宣称本次原生对象切换验收通过。

## 已核查实现与边界

### 后续视觉审查发现并已修复：P2 重复选择工作区域后只剩引线

来源：独立视觉审查反馈；本子代理随后仅复读 `src/holocue/viewer_scene.py:126-155,172-214` 确认控制流。

`select_view()` 第183行每次把 labels 设为不可见，末尾第214行调用 `update_annotations()`；若仍为同一 workspace 相机和姿态，第138-139行的 key 命中直接返回，不再恢复 label.visible。workspace 分支并未隐藏 leaders，故视觉症状是只剩引线；后续 tick 的相同 key 也不会自行恢复。

最小修复建议：`self.view_mode=mode` 后立即 `self.annotation_key=None`，让显式视图切换/重选失效布局缓存，普通 tick 继续复用缓存。局部控制流确认该方案充分；本段记录时尚未复读实际部署修复，不能算已关闭。

最终部署追踪：本子代理再次通过 SSH 读取服务器 Git diff，确认 `src/holocue/viewer_scene.py:180` 已部署 `self.annotation_key=None`，此前报告的缓存控制流问题在静态范围关闭。该文件 SHA256 为 `336b53785d732a05e0d3f06712a09b8323effc862a7fa377c4cc498c558bf71a`。真实重复选择标签验收结果另由主线程运行提供。

有价值回归：复用当前真实 Viser 客户端/SceneRenderer、固定会话和相机，依次 workspace、重复 workspace、detail/inspection、workspace；每次验证实际标签/引线可见状态。重复 workspace 时还应确认相机/姿态相同且引线端点未变。仅测 border_annotations 数值或断言 annotation_key 被置空不能覆盖实际可见性回归。受包禁止 mock 边界约束，本审查没有创建假句柄或绕过 renderer 构造器来代替真实运行。

### 后续候选补丁局部复审：原生审计聚焦前等待真实相机同步

主线程报告 blocks 原生前三阶段已采集，随后窄窗口/聚焦失败；原日志保留。主线程另观察过 resize 时 Python view 与真实客户端相机/aspect 不一致。该观察支持异步中间态假设，但本子代理没有独立复核对应失败原始记录，不能宣称聚焦失败根因已经完全证明。

本子代理读取本地 `current/scripts/tests/audit_bridge_live.py:186-243` 候选及服务器既有 `audit_viewer_live.py:32-88`。候选在显式视图按钮后等待 `CLIENT_READ` / `client_view_errors` 成功，再计算 expected_focus。既有检查比较真实 Three 相机 position/target/up/forward/fov/aspect 与 Python view，核对 CSS aspect、矩阵、drawing buffer 与默认 framebuffer；容差仍为 `1e-6`。读取过程不写相机或渲染状态，候选没有改变模型、任务契约或采样/渲染参数，静态逻辑能够拒绝已观察类型的相机不同步状态。

候选边界：一次采样通过并非之后相机永不变化的保证；外层25秒循环内 `self.view()` 可另等25秒，故整体不是严格25秒截止。`last_view_camera_checks.json` 会被下一次 select_view 覆盖；需要逐次因果证据时应使用唯一操作文件或累计记录。本轮没有将以上界限当作已证实的新功能缺陷。

本地 `current/src/holocue/viewer_scene.py:179-180` 同时已加入 `self.annotation_key=None`，位置符合上项最小修复。此次检查时两份均属本地候选、尚未部署，未计算或冒用服务器最终摘要；未执行模型、服务、渲染或测试。后续实际部署与受影响原生运行结果仍待主线程证据。

最终部署追踪：本子代理再次读取远程 `scripts/tests/audit_bridge_live.py:186-245` 及当前 diff，确认真实相机检查已落地；第206-208行改为以追加模式写 `view_camera_checks.jsonl`，每次包含 requested_at/mode/target/finished_at/checks，原覆盖问题已解决。既有聚焦契约计算和 `1e-6` 阈值保持。文件 SHA256 为 `8ae146ef45edc64de903ba78cf322b997497e2f73713454b74961f1552c3aa14`。对 resize 假设仍只作静态支持；当前 blocks_final、标签和 pytest_final2 在主线程执行，本审查不提前宣告其通过。

- 已读包 `CODEX_PROMPT.md`、`REVIEW.md`、`README.md`、`BASELINE.json`、`verification.json`；读取当前 Git diff 与新增生产/测试文件，核查基准提交。
- annotations：原有对象局部 label anchor 通过当前确认姿态转为世界坐标，边缘标签及连接线仅 workspace 显示，detail/inspection 均隐藏。分配使用真实投影、线性分配及单调间隔约束；本会话没有把数值矩形检查等同于原生字形或连接线遮挡验收。
- Viser：直接查阅服务器已装包 `_scene_api.py` 的完整 `add_label`、`add_line_segments` 实现/参数，以及客户端 `LabelRenderer.tsx`、`labelLayout.ts`。新增 `font_size_mode='scene'`、`font_scene_height`、`depth_test`、`center-left/right` 和 `thickness_units='screen'` 均存在于本机实际接口；空连接线 `(0,2,3)` 符合 shape 检查。没有发现参数名/API 兼容错误；这不是客户端运行验收。
- presentation：仅读取 Session.completed/queue/suspended；insert/assemble 历史按 target 取最近 reference，源对象与接收对象双向文案合理。未修改 Session、任务身份、模型提示、N/sigma 或任务契约。新增测试只证明状态转换文案，不证明 L1/SPARE 或 B/C 的真实模型流程。
- 材料：`partition_cad_parts` 逐项减去已有并集，保留首项优先材料分区。箱体继续使用原五面板尺寸、圆角；软管共享既有 lumen/roof 切除后再分区。新测试包含 CAD 双向差集、区域内部交叠、材料、非修改网格相等和有限外部射线。软管 0.6mm 是新增外表面再三角化检查边界，原动作 0.75mm 协议没有在这些修改中被改变。
- 断言变化：`test_engine_clamp.py:121-132` 不再要求三个材料区域各自单连通，而要求各闭合正体积、金属座单连通，以及物理软管 CAD 并集单连通；这与材料分区概念相符，不能表述为导出三个区域每个都单连通。其连通性依据是 CAD union；输出网格的检验仍是各区域闭合/流道有限采样，并非连续装配认证。`test_panel_optical_mounts.py` 的 BAY 原字节断言被局部五面板材料/外表面检查取代；非面板节点仍由新材料测试保持。
- GLB：`validate.cjs` 调用实际已装 Khronos `validateBytes`，`format='glb'`、`maxIssues=0`，通过 severityOverrides 将 `GLB_EXTRA_DATA` 设为 error；Python 包装对 numErrors 明确报错。sparse accessor 由 pygltflib 公共元数据明确拒绝；无依赖缺失 fallback。格式测试含合法、尾随、截断与 sparse 情况。未运行这些测试，真实测试结果由主线程记录提供。

## 独立源码摘要

本子代理在服务器以 `PYTHONDONTWRITEBYTECODE=1 .venv-simulation/bin/python -c ...` 导入旧包 `.work/incoming/repair_review_20260920_25bcc909/HoloCue_Repair_Review_Kit/tools/review_bundle.py`，调用其原始 `source_snapshot(Path.cwd())`，仅输出 JSON，不写服务器文件。

- 算法：`sha256-path-size-content-v1`
- 选中源码文件数：126
- Git HEAD：`c4463b3a9842b3945ab7d1582ab8e49fcadca245`
- 首轮修复前摘要：`144eb217ca914243fd631bdff095a55ed4ecd949f6d6cec2bc27fa48012f488d`
- 首轮两处修复部署后的第二轮摘要：`bd938aafb0b6e056bfecb53aa88ca189ae43d3724489194e34bfe53bffc3be24`（126文件、Git HEAD仍为基准）。
- 标签缓存/聚焦等待/追加日志全部部署后，本子代理调用同一 helper 独立计算的最终静态复审摘要：`b2c379ba354ce95e6e48d5a9e73f2ff5bcfecb22acf823b785101b6df5ea2457`（126文件）。
- 最后只读收尾核验的 Git HEAD：`7a7da494e05fa52a43ec27c5e3226d8c540196b1`，`git status --porcelain=v1` 为空。再次运行旧 helper 确认源码摘要仍为 `b2c379ba354ce95e6e48d5a9e73f2ff5bcfecb22acf823b785101b6df5ea2457`；两项最后修复已包含在该提交中。此前部署复审 HEAD `3871a85c17b0a22caf26dbddba340daa7a699d6d` 的 dirty 状态仅为历史时点。

旧 helper 不包含 tools，因此独立补充运行文件 SHA256：

| 文件 | 字节 | SHA256 |
| --- | ---: | --- |
| tools/gltf_validation/package.json | 145 | 2dcbbe578bb9103c6e2759d56745438f79204600719775e44b45adadc1e6a41e |
| tools/gltf_validation/package-lock.json | 611 | 4464fb72c7ee1fb3b44fe1747d91870ad71cdaca5639cd111958348e2d0adb96 |
| tools/gltf_validation/validate.cjs | 787 | b38563db0f735453214b46b3dcfb1b37e5fd250f6cedcddd0efe1112f4b28394 |

本机依赖 package.json 确认版本 `gltf-validator 2.0.0-dev.3.10`。额外核查 Node 实际 require 入口及编译实现：

- `tools/gltf_validation/node_modules/gltf-validator/index.js`：`78deff9ea85743e86461c2d14fae76e7fc3ca0432e652f62948066b55fa16f0d`
- `tools/gltf_validation/node_modules/gltf-validator/gltf_validator.dart.js`：`b73a7b2d455ac217567725138b46d826a13d7d1bb0c88c15f7c571bfb349298c`

最后部署复审同时重新计算了上表三项 tools 文件和两个已装 validator 运行文件，五项哈希均与首轮一致。以上最终摘要对应全部上述修复已部署的复审时点；如后续源码再变，需另算摘要，不能挪用本结论。

## 验证状态

本次子代理完成的是只读源码/API/摘要审查，不含服务启动、pytest、模型推理、资源竞争测试或新原生图像。云端478测试、旧431测试/63原生阶段均保持各自来源，本报告不为其添加“本次服务器通过”含义。资源守卫终止后应按包要求停止实验并列出未执行项。

第二轮复审时，主线程告知首轮完整 pytest rc=0，最终 pytest 与宽窄 UI 检查正在运行。本报告没有独立读取其最终运行证据，不将尚在执行的检查写为通过；这些结果以主线程最终证据记录为准。首轮两处已定位源码问题在静态范围内关闭；之后新增的标签缓存问题保持单独修复追踪。

最后部署复审时，三项源码 P2 均在静态范围关闭，原生聚焦前等待及逐次日志已确认部署。主线程报告的 pytest_final2/blocks_final/标签运行仍不属于本子代理独立执行证据；本报告没有新增任何测试通过数或原生阶段通过声明。

### 最后只读核验：pytest_final2 已完成

本子代理实际读取并以 XML 解析器核对远程 `runs/simulation/cloud_update_20260921_ce64aff5/pytest_final2.xml`：testsuite tests=519、errors=0、failures=0、skipped=0，实际 testcase 元素519个，failure/error/skipped 元素均为0；XML时间281.431秒。

同时读取 `pytest_final2_command/execution.json`：returncode=0，记录器耗时285.974722秒，起止时间为 `2026-09-21T07:29:02.017792+00:00` 至 `2026-09-21T07:33:48.408722+00:00`。命令经过原 `resource_guard.py --rss-limit-gb 8` 运行完整 `pytest -q`，使用 `.work/pytest_cloud_update_final2`。source_before/source_after 均为最终摘要 `b2c379ba354ce95e6e48d5a9e73f2ff5bcfecb22acf823b785101b6df5ea2457`；运行中 HEAD 从3871a85推进至7a7da49，内容摘要未变。assets_before/assets_after 同为 `36866cf33627a522897a66a3e1247587608d72959dc792d029de0136a0b78af8`。

证据文件独立 SHA256：

- `pytest_final2.xml`：`889f85af151e8128f70ddd49d04276f8f1201d25ecb7b8789ddafe1924902f69`
- `pytest_final2_command/execution.json`：`e5aa3d926d669adc34181e476a7ea86ac92ebc825d730ea4d2da454f5752eb5a`

这是本子代理对主线程本次服务器真实完整测试结果的独立只读核验，不是本子代理重跑测试。主线程另告知 blocks_final 已越过旧聚焦失败点，且 blocks 的宽窄标签/重复点击恢复检查通过，其余标签场景仍在执行；本轮未独立读取这些原生阶段/图像，不新增其通过数量，更不声称全十二场景原生流程完成。

### CNC 后续实际失败：单次相机匹配并不代表视图转换结束

本子代理只读核查 `bridge_batches/cnc_toolchange/cnc_toolchange/failure.json`、`stages.json`、`view_camera_checks.jsonl`、`focus_actions.json`、`api_reads.jsonl` 及 `runs/simulation/viewer/client_10_view.json`。failure记录 `Visible focus control did not focus the contracted target plane`，已有5个阶段（01_start_paused、02_middle_paused、03_temporary_inspection、04_original_restored、05_endpoint_waiting），browser_errors为空。这里仅核对记录，不代替逐阶段原生图像复验。

最后 workspace/T09 检查 requested_at=1789978651.0773563、finished_at=1789978651.4805372，仅一条 passed；该条实际相机位置 `[-0.47204704786848645,-0.524074492458437,1.189867525631491]`，而失败后实际导出 workspace 相机位置为 `[-2.059339302073441,-2.9136538940436223,2.367555344581125]`，focus=3.4274958833326816。相机后续发生明显变化，说明第一次客户端/Python同时匹配没有证明新视图已静稳。

本子代理对已有原始记录执行只读数值回算（无服务、模型、渲染、测试运行）：读取最后 snapshot revision15/epoch13 的 T09 object_pose 与现有 cue_offset_local_m，对首次 passed 相机投影得到期望深度 `0.36113566806642644m`；对失败后 workspace 相机投影得到 `3.4274958833326816m`，与真实导出的focus完全一致。此证据支持“期望值取到了较早相机，而聚焦按钮使用后续workspace相机”的诊断；后者聚焦数值本身符合最终相机下的契约。

限定修复方案只涉及 `audit_bridge_live.py`：要求真实客户端与Python相机持续匹配，且同一相机保持至少0.75秒，之后再计算焦点；不改变app、相机或模型参数。每次匹配失败或位置/目标/up/fov/aspect/矩阵变化均应重置稳定窗口，并覆盖不同 generated_at 的view及真实client采样，不能用重复旧view撑满时长。失败时持久化 expected_focus、用于计算的view/snapshot版本及末次actual view/client。该方案方向合理，0.75秒是显式有界静稳判据，不能证明任意延迟下都不会有晚到相机更新；需后续具体补丁复读和受影响真实运行。

本轮没有修改服务器代码、运行实验或修改上述最终源码摘要；最新方案尚未部署核验，因此此前519测试仍只适用于已记录的 `b2c379ba...` 源码。本报告保留新问题为待修复/验证状态。

### CNC稳定窗口最终部署复核与证据分层

随后本子代理重新读取远程 `scripts/tests/audit_bridge_live.py:197-263` 并核对 HEAD `ca213c5d6ea9bd3b9dc7f175cac7aefb7df22ff0` 的提交范围：仅该审计文件修改，27行新增、2行删除，工作区干净。文件SHA256为 `e8753bfde0e21a36fa670d671b4336fabe44bcc8d10eafaea740df6ba0b5e88f`。

代码现在要求实际 CLIENT_READ 与Python view每次匹配，位置/look_at/up/fov/aspect在 `atol=1e-7, rtol=0` 内保持，稳定持续至少0.75秒，并累计至少3个不同generated_at；任何匹配失败或相机变化会清空稳定区间/不同导出集合。日志逐样本记录 stable_camera_seconds、view_generated_at、distinct_camera_exports。聚焦超时另写完整 snapshot、expected_depth_m、focus_point_m、camera_before_focus 与 observed_view。源码逻辑符合拟定局部修复，没有改变应用、模型或渲染参数。其稳定窗仍为有界同步判据，不声称任意网络延迟下的形式保证。

再次调用同一旧 helper 的 source_snapshot，得到126文件、摘要 `37b81f92c4bb91b5ca68180be99b1f1810b40657842cf2d3145bd1eeb8d3f0fe`。这取代前文b2c作为当前源码身份；历史摘要和测试关联继续保留。tools/gltf_validation三个文件重新哈希仍与前表一致。

本子代理实际读取 `focus_settling_command/execution.json`（rc=0）、`focus_settling/report.json`、12项 focus_actions、12次 view_camera_checks，以及前后snapshot，并读取执行的 `.work/cloud_update_20260921/verify_focus_settling.py`。该执行复用 CNC 原失败会话 `4ce9f8e349e84c7ea305df2a1e16a443`，三个窗口宽度1600/1100/1600、高1000，各做 detail/workspace/inspection/workspace；执行脚本没有模型发送动作，前后snapshot解析后完全相同。12次焦点 observed 与 expected 最大绝对差为0，最后稳定区间最短0.7512653700541705秒。

必须保留源码阶段差异：上述12次执行 source_before/source_after 为 `2706c8ea2315fc4feac33909f65f08ee6f6fc87bea20a37597e4531ae60b21b5`，其camera日志尚无distinct_camera_exports字段。它证明连续稳定窗口前一版的12次真实切换通过，不能写成最终 `37b81f92...` 不同导出约束已通过。新完整CNC批次的最终约束验收仍由实际后续证据决定。同理，519项pytest只归属 `b2c379ba...`，不归属2706或37b8。

### 已观察限制：客户端断开清理竞态

本子代理实际读取 `viewer_command/stderr.log`，其中两个poll线程在 `src/holocue/viewer.py:313` 调用 executor.submit 时遇到 `RuntimeError: cannot schedule new futures after shutdown`。这与断开清理期间 stop/ready检查和executor.shutdown之间的竞态相符；其调用位置属于既有生命周期代码。本次证据没有说明它导致会话任务错误，也不能据此宣称服务完全无异常。按限定范围保留为清理竞态限制，不进行未授权的服务生命周期重构；UI/session无错误记录是主线程另行观察，不能代替stderr中真实异常。

### 最终只读核验：严格稳定条件越过旧失败点，资源守卫终止整场

本子代理实际读取 `bridge_batches/cnc_toolchange_final/cnc_toolchange/` 下的 `view_camera_checks.jsonl`、`focus_actions.json`、`stages.json`、`failure.json`、`exporter.log`，以及 `bridge_cnc_toolchange_final_command/stdout.log` 和 API守卫记录。新会话为 `0387d61e76634f8da309475aab6645f2`。

已记录9次相机检查和9次聚焦操作；各次末项camera检查均passed，稳定时间最短 `0.753260224009864` 秒，不同generated_at数最少4，满足最终 >=0.75秒且>=3不同导出要求。9次expected/observed焦距最大绝对差为0。旧失败位置T09 workspace在revision15/epoch13已得到expected=observed=`3.4274958833326816m`，并继续完成revision17/epoch15、revision19/epoch17的T09工作区阶段。因此最终约束已得到该实际原生路径验证，不再仅有前版12次局部切换证据。

`stages.json` 实际记录9阶段：01_start_paused、02_middle_paused、03_temporary_inspection、04_original_restored、05_endpoint_waiting、step_01_start、step_01_middle、step_01_endpoint、step_01_endpoint_receiver。stdout随后记录 `step_02_inspection capture started`，failure记录 `Exporter stopped during native Blender capture`；该阶段未列为完成。exporter.log结尾为 `httpx.ConnectError: [Errno 111] Connection refused`，不能把失败阶段计入通过或称CNC整场完成。

API因守卫停止的依据：`api_command/stdout.log` 两处守卫配置记录 `host_reserve_gib=50.30907897949219`；`api_resources.jsonl` 在time=1789981747.5597982记录API PID1777347的host_available_gib=`50.02719497680664`；`api_command/stderr.log` 明确 `Stopped only owned process group: host memory reserve reached`，并有Uvicorn正常shutdown记录。该证据支持资源阈值触发API停止，随后Exporter连接被拒绝的链条；不把共享主机内存压力归因于未核实的具体其他进程。

最后核对HEAD仍ca213c5、工作区clean。按包的守卫停止规则，后续实验停止；保留旧CNC聚焦失败、新CNC资源中断、清理竞态及未运行范围。519测试继续只归b2c源码，本报告不宣称新摘要全pytest通过、CNC整场完成或十二场景原生全部完成。
