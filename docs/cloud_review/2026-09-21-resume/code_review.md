# HoloCue 剩余任务续跑：独立只读源码与编排审查

真实审查代理标识：`/root/cloud_code_review`。本轮只读取服务器文件、已产生记录和进程元数据，独立计算摘要；未启动实验、模型请求或服务，未修改服务器代码。原审查报告保持原字节，本报告引用 [上一批源码审查](../cloud_update_20260921/code_review.md) 的问题追踪和历史证据边界。

## 当前结论

最终实际结果：CNC新会话完整18阶段报告通过；connector初始规划因模型连接失败而0阶段中断，后续5场原生和3组配对未运行。独立核实模型触发主机内存守卫，全部本批服务随后已停止且无重启。源码/资产前后一致。已发现并为后续队列修复一项P2场景边界缺口：本次模型守卫退出后仍启动了一次connector，该实际失败保留，不能表述为守卫触发后立即停止全部实验。新增边界检查在已关闭服务上按预期拒绝，未补跑。阶段内服务停止后当前阶段继续仍为未扩充的编排限制。

- 项目：4029 `/home/hdd3/zhanghaonan/projects/holocue`。
- 当前HEAD：`ea8c2f7838f7bf18fef6e5f64b83e641b5a0962e`，`git status --porcelain`为空。
- 新RUN：`runs/simulation/cloud_resume_20260921_ea8c2f7`。
- 独立调用旧 `review_bundle.py` 的 `source_snapshot(Path.cwd())`：126文件，算法 `sha256-path-size-content-v1`，摘要 `37b81f92c4bb91b5ca68180be99b1f1810b40657842cf2d3145bd1eeb8d3f0fe`，与上次最后版本完全一致。
- 当前HEAD的最新提交仅记录上一批归档清单，未改变上述源码摘要。

## 续跑边界核对

读取 `.work/cloud_resume_20260921/phase_env.sh`：先source旧phase_env，再仅覆盖RUN_DIR与HOLOCUE_STATE_PATH为新RUN及其 `state.sqlite`。旧phase_env继续读取 `.work/task_env.sh`，使用原 `.venv-simulation`、项目内缓存、`Qwen/Qwen3.5-4B` 服务配置和旧RECORD_KIT。实际读取API服务进程环境，HOLOCUE_STATE_PATH确为新数据库，未指向旧RUN数据库。

读取 `run_remaining.sh`：`set -e`，顺序运行 cnc_toolchange、connector、control_panel、dig_site、dive_fillstation、drone_bench、infusion_ward 七场，其中CNC为未完成整场的重新完整运行，其余六场为剩余范围；随后仅运行 engine_bay、shelf_picking、dig_site 三组既定配对。每项经旧 `record.py`，任一非零返回立即停止队列。没有重跑已通过blocks、pytest、十八条路径、标签或构建的命令。

配对入口 `capture_changed_pairs.py` 的输出由当前RUN_DIR生成，并用 `exist_ok=False` 创建；续跑清单没有硬编码写回旧运行目录。既有record.py的暂停标记约束仍保留，读取时该旧暂停标记不存在；本会话未删除或绕过它。

读取 `readiness.py`：核验所记录model/api/viewer进程PID与创建时间，再GET三个就绪入口，写新RUN的readiness.json；不发送模型任务，也不伪造服务响应。600秒总时限到期明确报错。读取时最后一条记录time=1789990948.0089545，API与viewer为200，model仍ConnectError；模型日志当时正在加载权重。因此本报告只确认就绪检查机制及当时状态，不将启动过程提前表述为全部服务就绪。

## 裸启动器拒绝与实际守卫链

读取 `.work/cloud_resume_20260921/ORCHESTRATION.md` 的初次失败记录：把裸start_ui.py交给record_command时，工具以 `ValueError: Invoke the existing resource_guard.py with --execute as the recorded command` 拒绝，返回码1；主线程记录该次未启动服务。

本子代理独立读取旧 `record_command.py:29-38`：guard强制检查在 output.mkdir、source_snapshot、subprocess.run 之前。因此该失败边界的控制流与“未执行裸启动器”一致。原工具没有放宽：实际三个started.json的recorder_sha256均为 `e10d17d1fa576e0373933d0803ee0f4e1844172a9a7b81a04fe2483041fa78e0`，bundle_tool_sha256均为 `65b69df894c346ab8d9684e156d6ed48a6387f4ea05e3b948c93a49253f6072c`，与前批一致。本报告不伪造一份未保存的首次失败execution.json。

随后直接运行的既有start_ui.py仅编排model/api/viewer，各自调用旧record.py。独立读取三个started.json并用psutil跟踪已记录PID的实际后代，均存在以下链条：`record.py → 旧record_command.py → resource_guard.py → 原服务脚本 → 服务自身resource_guard → 实际服务`。model外层RSS32GiB，API/viewer外层RSS8GiB；内部原守卫也保留。启动器本身没有外层长期守卫，不意味着服务未受守卫管理；实际各服务均独立受约束和记录。

实际进程/创建时间：model launcher PID1877576、1789990857.54；API PID1877577、1789990857.55；viewer PID1877578、1789990857.55。实际服务子进程包括模型API PID1877630、HoloCue API PID1877607、viewer PID1877608。这里只记录本轮已观察身份，不用于授权操作其他进程。

模型实际命令仍为本地 `.venv-model`、`models/Qwen3.5-4B`、vLLM、物理GPU1、GPU_FRACTION0.70、max-model-len8192、max-num-seqs1、原qwen3 parser/thinking设置。内部模型守卫仍要求host-reserve32GiB、RSS32GiB、min-gpu-free12GiB；预检记录授权GPU1/2、实际主机保留线50.30907897949219GiB。没有降低原阈值、切换模型或改用CPU模型。

## 编排文件补充摘要

旧source_snapshot不包括.work中的编排脚本，故独立补充SHA256：

| 文件 | SHA256 |
| --- | --- |
| .work/cloud_resume_20260921/phase_env.sh | 97893fffcb815b282d0894ae860f161e187b7335c1bd08855821fe09a967fa2c |
| .work/cloud_resume_20260921/run_remaining.sh | 1ed7dc0d3b224f4e4e38bbb739de71171b0c119ab1076cc99fe97a72e6aa1ad3 |
| .work/cloud_resume_20260921/readiness.py | 7d40c43c6a39f33023e9242a1177807ebae4e71d2a2534d33e33d30c96454c49 |
| .work/cloud_resume_20260921/ORCHESTRATION.md | 2efff45bc7a7eea19e890cc2e2e4f9c27488ecb9b1e66c713c4ef5959503671a |

tools目录三项重新哈希，与旧报告一致：package.json `2dcbbe578bb9103c6e2759d56745438f79204600719775e44b45adadc1e6a41e`；package-lock.json `4464fb72c7ee1fb3b44fe1747d91870ad71cdaca5639cd111958348e2d0adb96`；validate.cjs `b38563db0f735453214b46b3dcfb1b37e5fd250f6cedcddd0efe1112f4b28394`。

## 证据边界与保留限制

上一批519 pytest通过仍仅归属b2c源码；当前37b8续跑不重复宣称完整pytest通过。旧CNC资源中断、先前聚焦失败和客户端断开清理竞态继续保留，不因用户重新授权而抹除。本轮仅核对新目录编排与运行身份，没有重新哈希所有旧ZIP，因此不将“未写旧目录”提升为对全部旧归档字节的再次验收。

此时剩余原生场景和配对尚待真实运行/视觉审查。若本轮资源守卫再次终止，继续遵守既有停止实验规则，保留已产生资料及未执行项；本报告没有为失败后自动重启或降低阈值提供授权。

## 最终实际运行与停止核验

本子代理实际读取model/api/viewer/CNC/connector/shutdown的execution.json、两场report.json、CNC final.json、model资源/错误日志、RESOURCE_STOP.json、service_shutdown.json、shutdown_gpu_ports.json。再次调用原review_bundle的source_snapshot和asset_snapshot：HEAD仍ea8c2f7且clean，source=`37b81f92c4bb91b5ca68180be99b1f1810b40657842cf2d3145bd1eeb8d3f0fe`，asset=`36866cf33627a522897a66a3e1247587608d72959dc792d029de0136a0b78af8`。上述六个execution的source_before/after及assets_before/after均分别等于这两个摘要。

CNC记录：新会话 `4bf040f621e240b2b9a618a9f18a0755`，command rc0，report passed=true、18阶段、browser_errors=[]；final为idle，queue/suspended均空，revision22/epoch20、completed4。包括上批中断的step_02_inspection和最终workspace及对象视图。本审查核查运行记录，不替代另外的视觉原图审阅，也不把旧CNC会话拼成本次结果。

connector记录：会话 `a3aaea69f033449f89b3a10ecd97adad`，command rc1，0阶段；状态revision2/epoch1、execution=error、last_error=`PlannerError: ConnectError: All connection attempts failed`。后续control_panel、dig_site、dive_fillstation、drone_bench、infusion_ward五场未运行，engine_bay、shelf_picking、dig_site三组pairs未运行。

模型守卫真实因果：model_command/stderr.log明确 `Stopped only owned process group: host memory reserve reached`；原保留阈值50.30907897949219GiB，实际1789993727.6362495（2026-09-21T12:28:47.636250Z）available为50.28264236450195GiB。该条模型RSS5.0338630676GiB、GPU1占用15672MiB/24576MiB；停止原因是主机reserve触发，不能误报模型OOM或GPU越界。model执行12:28:53.184225Z结束rc1，原阈值与参数未改变。

### 已修复后续场景边界的P2：独立模型守卫已结束，场景队列仍启动下一场

执行时旧 `.work/cloud_resume_20260921/run_remaining.sh:4-6` 只检查每个audit的返回码，没有检查长期服务守卫的退出。日志时序明确：model结束12:28:53.184225Z；CNC凭已有计划继续，12:32:35.184779Z返回0；connector12:32:36.212124Z启动，到12:33:13.702029Z因初始真实模型请求连接失败返回1，set-e才停止后续队列。

这是一项已发生的编排停止边界缺口，不能被当前已停止状态掩盖。主线程已决定只为未来续跑增加每场景/pair前的服务guard执行记录与owner身份检查；保留已执行脚本原字节及SHA，不能抹除connector实际启动/失败。当前不为修复该编排问题重新启动服务或补跑。

实际修复复审：本子代理读取新的 `.work/cloud_resume_20260921/require_services.py` 与run_remaining.sh，确认每场scene/pair前检查model/api/viewer的execution.json不得已存在，并核对记录owner PID/create_time且非zombie；任一失败直接非零退出。原执行脚本已保存为新RUN的 `run_remaining_executed.sh`，独立SHA256 `1ed7dc0d3b224f4e4e38bbb739de71171b0c119ab1076cc99fe97a72e6aa1ad3` 与首轮所读字节一致。新run_remaining SHA256为 `2d920527071e3637e6324e027abffcb943c8edc5a1096e6c8c9ecedaba25376f`，require_services为 `094232b9425adf6bd1378c66a8981eaace33f7d648b4b719b00f3c40b6d1b707`；仅.work helper变化，源码/资产摘要不变。

已实际读取stopped_boundary_check_command的execution与stderr：该只读检查经旧record/guard运行，returncode=1，明确拒绝已完成model recorder，未启动任何实验。此处1是预期拒绝，不能写成服务或原生测试通过。该局部修复覆盖本次“模型早已退出但仍开始下一场”的触发路径；它不是跨阶段事务或全生命周期监控，不能消除检查之后服务恰好退出的竞态，也不会立即取消正在运行的场景。上述范围限制与本次connector真实失败继续保留。

### 停服务证明

shutdown经旧record.py→resource_guard执行既有stop_services.py，rc0，12:33:58.029069Z完成。stop_services源码按本批记录owner PID/create_time核验后只对后代服务发信号；service_shutdown记录model已退出，viewer/API分别仅对PID1877608/1877607发SIGINT，remaining_owned_processes均空。viewer service command rc254对应该次信号关闭，API rc0；不能将viewer退出码写成无异常自然结束。

shutdown_gpu_ports记录8000/8750/8780已关闭，GPU1/2各4MiB。本子代理随后独立只读socket连接检查三端口均返回111，并检查三个记录launcher PID均已不存在。未重启模型/API/viewer，未运行新实验；旧批归档/报告未覆盖。

另实际读取verify_cleanup_command：原守卫包装只读verify_owned_cleanup.py，rc0，stdout报告passed=true、22个记录身份已核验。以上停服务证明与本子代理的现场端口/launcher核查一致。
