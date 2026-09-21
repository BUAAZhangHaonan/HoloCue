# 续跑最终来源审查（2026-09-21）

独立会话：`/root/cloud_provenance_review`。本轮只读核对新RUN选择、命令记录、封存继承证明、结果与原始事件；没有运行项目实验，没有重复旧资产全扫描。**当前交付来源与实际范围可接受；新增CNC完整通过，connector失败，剩余5场及3组配对未运行。新ZIP尚待打包后的成员哈希/CRC复核。** 本节优先于后附启动时快照。

## 源码、资产和命令身份

本次复算source_snapshot仍为 `37b81f92c4bb91b5ca68180be99b1f1810b40657842cf2d3145bd1eeb8d3f0fe`，与source_final逐文件清单一致；HEAD=`ea8c2f7838f7bf18fef6e5f64b83e641b5a0962e`，工作区干净。资产身份 `36866cf33627a522897a66a3e1247587608d72959dc792d029de0136a0b78af8` 复用本轮已经独立实际散列的103项基线，不重新读旧大资产。

对首次最终selection的 **60个run、1995个显式文件** 通过原Selection严格模型及路径规则校验，逐条读所有已关联command。新current分类均同时满足源码before=after=当前、资产before=after=当前；其passed/failed与实际returncode一致，没有不一致路径、run引用或当前身份。旧run均为previous_前缀/historical/recorded，保留真实旧source、asset及失败结果。后续仅添加最终报告/文档记录的selection需要按增量纳入，不应改变这些结果。

selection_command本身实际returncode=0；开始2026-09-21 12:37:48 UTC、结束12:38:13 UTC。该执行完成包含修复后的封存文件字节核对，不代表项目实验通过。

## 封存证据继承

独立读取旧00_review_index.zip，SHA256仍为 `41eddc0d64ffaa07001646796baa2eded5987a7289775b0a00438b93c1bc66a5`，大小/摘要与published UPLOAD_INDEX和新inherited_evidence_verification一致。独立将新证明中的 **1582条继承路径、大小、SHA256** 与ZIP内 `HoloCue_Review/MANIFEST.json` 逐项比较：全部相等，且每项都在新selection中。

本审查核对的是“成功执行的逐文件字节验证记录→封存manifest→实际小索引ZIP”这条来源链，未再次重复散列1582份历史文件。运行时逐文件读入比较由已审查修复且returncode=0的选择器执行；本审查没有把证明字段的passed单独当成证据。

新COVERAGE的reused_checks中tests/geometry/native_builds与旧COVERAGE完全相同；每场earlier_batch对象也完全相同。此前519项pytest及blocks/12场labels仍归b2阶段，geometry和三份build仍归144阶段，不冒称本轮37b8新运行。旧ZIP未改。

## 新实际结果与原始材料

| 新流程 | 实际身份与结果 |
|---|---|
| CNC | 会话4bf040f621e240b2b9a618a9f18a0755；18阶段；returncode=0、passed=true |
| connector | 会话a3aaea69f033449f89b3a10ecd97adad；0阶段；returncode=1、passed=false；首次请求PlannerError ConnectError |
| control_panel、dig_site、dive_fillstation、drone_bench、infusion_ward | 未运行 |
| engine_bay、shelf_picking、dig_site定向配对 | 未运行 |

旧blocks与新CNC合计完成规定8场中的2场，但两个通过结果来自各自阶段，不能称同一最终源码8场完整验收。

- 18阶段的 **36份新原始配对图**（frame_0000.png/viser.png）全部显式选入，并归bridge_cnc_toolchange。
- 两份本次WebM均选入，未发现漏选本次视频：CNC原视频43,853,692字节，connector失败视频543,464字节；分别归各自run。没有为本次原视频派生转码。本检查证明选择/大小，不重复进行视频逐帧视觉判定。
- CNC events.json包含两次真实Qwen/Qwen3.5-4B plan_committed，保留raw_http_body（2092、1123字符）和raw_response（1203、359字符），不是仅有解析后计划。connector events_on_failure.json保留turn_error、实际request_body、prompt_sha256、latency及ConnectError。两个事件文件均选入。
- 实际36张图不等同所有视角均合格。独立视觉报告关于接收位置侧壁遮挡、孔内不可见/上部裁切和POCKET9已占用的限制仍有效；本来源审查没有覆盖这些视觉结论。

## 第二次实际资源停止、拒绝边界与清理

RESOURCE_STOP引用的7份原始文件已独立读hash，全部匹配且选入。2026-09-21 12:28:47.636250 UTC模型守卫记录可用内存 **50.28264236450195 GiB < 50.30907897949219 GiB**，模型退出returncode=1。CNC使用既有计划完成，connector随后首次请求连接失败。此因果边界与日志/时间和报告一致；不能改写为额度耗尽、预防性停止，或把后续内存回升当作本批未触发停止。

stopped_boundary_check实际returncode=1，selection正确保留current/failed。stderr明确：`Refusing next phase: model recorder already completed`。它验证的是已停止服务下拒绝发起下一阶段，**不是新增实验通过**。主会话随后仅增加说明注释，保留rc1/failed分类。

owned_process_verification记录22个PID+创建时间身份全部exited，live_owned_identities为空；关闭记录8000/8750/8780关闭，物理GPU1/2各4 MiB。清理报告针对本批记录身份，不扩大成对全机所有进程的结论。

## 交付结论与后续范围

本轮限定来源审查未发现未闭合来源缺陷。修复后的helper静态报告另附；旧编排在模型停止后仍发起一次connector的实际失败和后续服务边界修复均被如实保留。新启动基线中“模型加载中”是早期采样，最终readiness已实际returncode=0；没有沿用早期未就绪结论替代最终事实。

主会话应把本最新报告同步到新RUN并纳入最终selection。新ZIP尚未生成，本报告不声明其成员hash/CRC通过；待打包后独立执行包级复核。先前封存18ZIP已复核结果继续有效，不必重扫。

本轮完整读取清单/哈希、source身份、run判断、封存继承比对、选入原图/视频、真实原始事件与拒绝日志保存于：

| 本地证据 | SHA256 |
|---|---|
| provenance_resume_final_inputs.json | 41ad9aad52c4fb80020cda7749416739349ab1240b63322e13b3a12e59618277 |
| provenance_resume_final_checks.json | 0624e2cc5512c0440a51251148bd8d80f53299605d4de9d1d0f2c2956d127056 |

---

以下保留启动基线原文，涉及就绪状态的表述仅适用于其采样时刻。

# HoloCue 续跑来源基线独立审查

独立会话：`/root/cloud_provenance_review`。采样日期2026-09-21，续跑目录 `/home/hdd3/zhanghaonan/projects/holocue/runs/simulation/cloud_resume_20260921_ea8c2f7`。本审查仅只读散列、读取启动记录及实际进程环境；未启动服务/实验，未覆盖旧报告、旧RUN或已封存18ZIP。

**结论：续跑代码、资产与上一批封存来源一致，新数据库独立，服务启动命令及资源规则一致。当前只建立启动基线，不是续跑验收通过。**

## 独立复算

- HEAD=`ea8c2f7838f7bf18fef6e5f64b83e641b5a0962e`，git status为空。
- 调用原Review Kit source_snapshot：`37b81f92c4bb91b5ca68180be99b1f1810b40657842cf2d3145bd1eeb8d3f0fe`。摘要及逐文件path/size/content清单均与旧RUN的source_final.json完全相等；HEAD变化未被误作源码变化。
- 调用原asset_snapshot重新读取实际文件：`36866cf33627a522897a66a3e1247587608d72959dc792d029de0136a0b78af8`。103项逐文件清单与旧assets_final.json完全相等：76活动GLB、27fixture（原22和新增5）。没有重建、修改GLB或覆盖fixture的迹象。
- 原算法仍不覆盖tools和.work helper；不能由上述source digest推出所有辅助脚本的历史版本相同。此续跑记录保留实际argv与选定环境。

## 新数据库与实际服务

新数据库 `/home/hdd3/zhanghaonan/projects/holocue/runs/simulation/cloud_resume_20260921_ea8c2f7/state.sqlite` 已存在，采样大小32768字节。实际model/API/viewer进程的HOLOCUE_STATE_PATH均指向该新路径，RUN_DIR指向新RUN，与旧cloud_update的数据库路径不同。仅存在文件不等于任务完成，本报告不作此推断。

逐一将旧/新started.json中的本轮RUN路径替换为占位符后，model、API、viewer的完整启动argv均相等。实际进程树亦核实：

- 模型PID1877630：项目Qwen3.5-4B，vLLM0.29.0，127.0.0.1:8000，TP=1，max_model_len8192，max_num_seqs1，GPU fraction0.70，qwen3 parser，enable_thinking=false，enforce_eager，image1/video0；CUDA_VISIBLE_DEVICES为物理GPU1 UUID `GPU-7ba69fc7-12ac-3dfb-8265-3476ce2504b6`。
- API真实进程命令为holocue.api，127.0.0.1:8750，守卫RSS8 GiB；viewer PID1877608为holocue.viewer，127.0.0.1:8780，守卫RSS8 GiB。
- 模型外层和内层守卫RSS均32 GiB；内层明确--gpus1、--gpu-fraction0.70、--min-gpu-free-gb12。预检实际授权物理GPU1/2及其UUID，returncode=0。
- 预检报告实际host_reserve_gib仍为50.30907897949219；没有把命令中的--host-reserve-gb32误写成实际有效保留阈值。原resource_guard源码与封存source清单一致。
- 实际HF_HOME、XDG_CACHE_HOME、TMPDIR、PYTHONPYCACHEPREFIX、TORCH_HOME均位于项目.work目录。此为实际进程环境检查，不是全系统写入跟踪。

启动时readiness记录保留了model ConnectError及后续API/viewer200。最后读取记录time1789990993.8489044时，API/viewer为200，model仍ConnectError，模型日志显示正在加载；readiness尚无完成execution.json。本基线因此**不宣称模型已经就绪或新任务已经通过**。该采样host_available为127.39706420898438 GiB，高于50.30907897949219保留阈值。主线程更早观察到的243.6 GiB不是恒定状态，不能持续沿用。

## 旧结果复用与续跑界限

旧cloud_update RUN、旧18ZIP及旧来源报告保持封存，不重复扫包。其独立包级核验已通过，但不改变各实验自身源码阶段：

| 复用材料 | 保留的原阶段及范围 |
|---|---|
| blocks_final | b2c379ba阶段13阶段完整通过 |
| pytest_final2 | b2c379ba阶段519项通过 |
| geometry与3份新静态blend | 144eb217阶段；3份build输入和输出来源已核 |
| 12场标签 | b2c379ba阶段，blocks来自labels_final，其余11来自labels_final_r2 |
| 旧CNC_final | 37b81f92阶段9阶段后实际资源停止，整场未通过；不升级为本次续跑结果 |

本次授权续跑CNC、connector/control_panel/dig_site/dive_fillstation/drone_bench/infusion_ward六场完整原生，以及engine_bay/shelf_picking/dig_site三组定向配对。各新会话、返回码、截图、视频和实际终止原因应归新RUN；本报告尚未审查这些后续完成证据，不把计划列为完成。

## 审查材料

provenance_resume_baseline.py为实际只读复算程序，经PowerShell文本管道运行远端已有.venv-simulation/bin/python -B；JSON保留完整source/assets清单、所读文件hash、启动命令、实际进程树与新DB路径。provenance_resume_startup.json保留旧/新argv对比、guard输出和有时效的readiness采样。

| 本地证据 | SHA256 |
|---|---|
| provenance_resume_baseline.py | 710cba507fa86066d9e25c4166d548bb2bcb3454a226aae0b460124081390d67 |
| provenance_resume_baseline.json | 244c57d6452e8208fe118c27e088fec2ffb320e24f918800ca41352398782ccb |
| provenance_resume_startup.json | 1cae0f82c1346f40ed197f65cc67ea8ddfa46f2a8a0122aded8ce6dd301d8632 |
