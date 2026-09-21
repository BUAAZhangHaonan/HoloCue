# 最终来源审查结论（2026-09-21 09:19 UTC）

独立会话 `/root/cloud_provenance_review` 的限定只读最终复核完成。**截至本次最终selection，来源分组和验收范围记录可以交付；这不代表全部原生验收通过，也不代表尚未生成的ZIP已通过完整性核验。** 以下结论优先于所有后附阶段记录。未启动新实验、未改远程实现、未重跑pytest。

## 当前代码与实际测试阶段

独立调用原Review Kit的source_snapshot复算：`37b81f92c4bb91b5ca68180be99b1f1810b40657842cf2d3145bd1eeb8d3f0fe`；HEAD=`ca213c5d6ea9bd3b9dc7f175cac7aefb7df22ff0`；git status为空。与source_final一致。

| 证据 | 实际源码阶段 | 当前可支持结论 |
|---|---|---|
| geometry及3个静态build | 144eb217… | 当时18条动作采样审计和3份构建来源；不是最终37b8重跑 |
| pytest_final | bd938aaf… | 519项通过，已有独立XML核验 |
| pytest_final2、12场标签、blocks_final | b2c379ba… | 519项通过；12场有完成捕获条目；blocks 13阶段完整通过 |
| focus_settling | 2706c8ea… | 中间阶段记录，不升级为最终源码验收 |
| CNC_final | 37b81f92… | 9个已记录阶段后中断，returncode=1、passed=false |

最新源码仅保留其本身实际运行身份，未把519项b2阶段测试、b2标签或blocks结果改称37b8执行。geometry/build输入来源与现有资产哈希关系保留；9份历史blend未冒称本轮重建。应用/资产不变不能替代同最终源码完整原生验收。

## 实际资源停止与未运行范围

独立读取RESOURCE_STOP列出的6份原始证据，SHA256全部匹配并已选入。API stderr原文含 `Stopped only owned process group: host memory reserve reached`。日志记录时间1789981747.5597982：主机可用内存50.02719497680664 GiB，低于50.30907897949219 GiB保留阈值；随后CNC exporter连接失败。停止依据是实际资源条件，不能改写为额度或主动提前结束。

- blocks_final：b2阶段，会话 `56bae844371f49fda588793e1bc1797f`，13阶段、returncode=0、passed=true。
- CNC_final：37b8阶段，会话 `0387d61e76634f8da309475aab6645f2`，9阶段、returncode=1、passed=false。保留中断材料，不算整场完成。
- connector、control_panel、dig_site、dive_fillstation、drone_bench、infusion_ward六场完整原生未运行。
- engine_bay、shelf_picking、dig_site三组定向配对未运行。最新FINAL_SUMMARY已明确写“未运行”，不再使用“未运行或未通过”。

service_shutdown中model/viewer的remaining_owned_processes为空，API记录owner_already_exited；shutdown_gpu_ports记录8000/8750/8780关闭、GPU1/2各4 MiB。这是受检停止记录的结论，本审查未重新启动或干预任何服务。

## 最终选择与来源修复验收

初次最终复核对1558个显式文件、45个run执行Selection模型、路径规则和来源关系检查：无缺失路径、无无效run引用；current/historical判断与每条实际command的源码前后摘要、资产after摘要和returncode一致；COVERAGE每项就近source/assets/returncode均与原execution一致。发现3个 `*_repair_process.json` 的suffix重复匹配残留，立即反馈。

主会话加break修复并重建selection。限定复查最新 `selection_reviewed_command/execution.json` returncode=0，before/after均37b8；最终 **1565个显式文件、46个run**。api/model/viewer的repair_process分别正确归属api/model/viewer；新增最终code_review、visual_review、NEXT_REVIEW_PROMPT及provenance报告路径已选入。旧两个P2及本次残留suffix问题均已在实际selection中闭合，历史发现记录留在本文件后部。

当前分组明确区分cloud_package、prior_c4463b3、export_toolkit、各实际执行阶段和delivery。RESOURCE_STOP归resource_stop，archive_relocation归archive_mapping；新旧viewer资源分别归viewer/viewer_phase1。archive_relocation的7条归档映射全部重新确认哈希匹配且已选入，旧内部路径字符串由映射解释，未伪造重写原记录。

## 已选入材料与范围

- 活动资产/fixture由原pack自动选择，非要求全写进selection.files。assets_final含103项：76活动GLB与27fixture。与本审查先前直接读取的资产/fixture哈希比对无差异；保留22原fixture、4个指定更新GLB/72不变活动资产及5个新增material_regions文件的来源。按要求本轮没有重复全读大fixture。
- 三份新engine_bay、shelf_picking、drone_bench `.blend` 明确归其build run，原pack将其分入native；9份历史静态构建保留历史来源说明。
- tools/gltf_validation的package.json、package-lock.json、validate.cjs均明确选入，当前散列与source_supplement匹配；旧source算法不覆盖tools的限制保留。
- 显式选择包含329张图片、34份原始WebM；只读枚举本轮视频后未发现漏选原视频。最大原视频37,502,530字节，review_videos/index为空，无需转码。本结论证明路径选择与大小，不是新增视频逐帧视觉审查。
- optical_bench、server_rack、control_panel的http.json、planned状态、操作记录、截图和视频已选入。独立解析http内plan_committed事件，确实包含Qwen/Qwen3.5-4B的request_body、raw_http_body、raw_response、prompt_sha256及usage；不是仅有解析后计划。模型流程仍保持bd938身份，后续只读检查不冒称重跑模型。
- 本轮失败目录、执行退出码、资源停止原文、原始配对PNG/消费帧/相机与状态记录被保留；分层PNG和EXR中间产物按说明留服。没有把“输出文件存在”当作整场验收通过。

旧source_snapshot不含.work辅助脚本。交付当前helper字节及其哈希，不能证明未封存的早期失败helper精确版本；该限制在REVIEW_NOTES中明确。标签整体命令失败和单场完成条目分开，12场捕获不等于12场模型或原生验收。

## 尚待打包阶段核验

目前只完成最终选择、来源和范围复核。**ZIP尚未生成，ZIP数量/大小/CRC、成员哈希和解压完整性待实际打包后核验**。主会话需将本最新报告同步到已选中的两个报告位置；本报告本身更新不改变项目源码摘要，但最终包应保存这版字节。包级核验不得引用本轮选择检查冒充。

本轮读取记录与可追溯散列：

| 本地复核证据 | SHA256 |
|---|---|
| provenance_final_selection.json | 37a3aefe5005dc9933790c66e6be544d315e969e3ba7ad24de188e7cae3107ee |
| provenance_final_selection_checks.json | 08321c19336d767e66c0d0f798fdc116cc81d10acc6cd7163d7658801675eef9 |
| provenance_final_selection_recheck.json | 7375d633d867cf1b3060c4a7464e79a5d8f3f3331a2aad20823b743367aa3b51 |
| provenance_raw_reply_check.json | dd9584ebb7bdab41ea25bbc487f05fef0f66e94d0d610d9f7faf99b5316d32ad |

---

以下为按时间保留的旧审查记录，最终适用结论以本文件开头为准。

# 打包来源修复复查（2026-09-21 08:14 UTC）

当前结论：上一轮两项P2在已读最新准备脚本中均已修复；这是具体代码逻辑和已有归档记录的只读复查，**最终selection、生成的COVERAGE及实际分包仍待验**。下方旧问题记录为发现时版本，保留作为审查过程，不代表当前仍未修复。

本地与远端 `.work/cloud_update_20260921/prepare_delivery.py` SHA256一致：`6e99747a3c9e217833f8e126a11d5ac34f9d3791afe33ceab7b55559a5fb544b`。本地 `REVIEW_NOTES.md` SHA256：`b5007c8d5521260d0ee779291835f971fc45a60c18a662c7495554244881a359`。

- **P2文件归属：代码层已修复。** prepare_delivery.py:42–45、65–75为geometry/XML、资源、服务owner/launcher、blender图、payload、build_provenance添加真实run映射；旧viewer_phase1和新viewer分别映射各自run。最终需核对实际selection没有错误回落delivery的关键执行证据。
- **P2就近来源身份：代码层已修复。** prepare_delivery.py:106–135的identity保留实际command_record、returncode、source_before/after、assets_before/after及源码阶段，并直接挂在geometry、native_builds、各pytest、native、targeted_pairs、label结果旁。label目录存在已不再代表完成：必须在该组report的scenes中找到条目，才标scene_capture_completed；单场完成另与整条命令returncode分开。最终需核对生成值是否符合实际记录。
- **viewer归档：已有实际映射及执行记录。** `archive_mapping_command/execution.json` returncode=0，开始07:53:10 UTC、结束07:53:12 UTC，before/after均为最终b2c摘要。`archive_relocation.json`含7个原路径→归档路径→SHA256/bytes映射；全部与本独立会话上一轮直接读取归档文件所得哈希和长度一致。映射文件SHA256=`8e39278ab2364276f3cd74a76cc988fe199cacd8a36c3f006b5d55cc0b37743b`，execution文件SHA256=`d2d3074aed1f6b596aaca8b4d7198c43d1a2f823aee485eabdc922ec56565a7e`。最终需确认映射与7个归档文件均被实际选入并保持这些字节。
- **helper边界：文档已明确。** REVIEW_NOTES说明旧source_snapshot不含 `.work/`；当前回传helper字节不能替代未封存的早期失败helper版本。因此命令记录证明项目源码/资产身份，不证明每个未封存helper的精确运行时版本。prepare_delivery.py:89的“original bytes”应按交付时当前文件原字节理解，不能赋予历史helper身份；REVIEW_NOTES已明确限制此解释。最终labels_final_r2 helper冻结是主会话声明，本轮未新增运行时实验验证该声明。

本轮没有启动prepare_delivery/export，没有重复fixtures扫描，没有检查仍运行原生的最终完成，也没有改实现。读取文件摘要和原归档映射另存 `provenance_delivery_fix_review.json`。最终待验明确包括：selection模型与run引用、最终各项scope/returncode/来源对应、tools三文件和helper身份、归档映射覆盖、最终分包hash/CRC/成员覆盖、最终原生/标签真实完成范围。

---
# 最终代码冻结后补充审查

本补录优先于下方07:13–07:15 UTC阶段快照；下方 bd938aaf 不再代表最终源码。独立会话仍为 `/root/cloud_provenance_review`，本轮仅只读复算和审查打包脚本，没有新实验或代码修改。

- 独立复算最终源码：`b2c379ba354ce95e6e48d5a9e73f2ff5bcfecb22acf823b785101b6df5ea2457`；本地远程仓库HEAD：`7a7da494e05fa52a43ec27c5e3226d8c540196b1`；git status为空。主会话称该HEAD已推送，本审查核实本地远程仓库状态，未另查托管端ref。
- `pytest_final2_command/execution.json` 实际 returncode=0，source_before/source_after均为上述b2c摘要；独立解析 `pytest_final2.xml`：519个testcase，0失败、0错误、0跳过，281.431秒。
- 相对上一版bd938aaf，源码清单又变更 `scripts/tests/audit_bridge_live.py` 和 `src/holocue/viewer_scene.py`。所以原阶段报告“仅annotations/viewer/test_annotation_layout三文件变化”的句子只适用于144eb→bd938这段，不能用于144eb→最终b2c。原geometry和3个build仍为144eb阶段证据，原生/labels须按最终执行记录判断。
- 未重复全读fixtures；其22文件不变的独立核验仍是07:13采样结论。本轮补录不把早先采样时间改写为新时间。
- 已读取并散列 `viewer_phase1_command/*`、`viewer_phase1_resources.jsonl`、`viewer_phase1_launcher.log`、`viewer_phase1_process.json`、`viewer_phase1_shutdown.json`；完整归档位置/哈希在 `provenance_final2.json.viewer_archives`。旧execution内部原始路径不可冒认为重启后的新viewer文件，最终打包仍须显式提供原路径→归档路径→哈希映射；此补录没有重写旧记录。

## 打包脚本只读审查结果

审查版本：prepare_delivery.py SHA256=`6bb4346ac7ad44ab366c6969b769fbf6a94d3264cf5058ec8aefe13911a69e53`；export_review.py SHA256=`64adb72e7b66af7501fd7342091385c9dded9ae85559859ac12cb4ea6c63b6c9`。以下定位只对应这两个版本。

**P2，prepare_delivery.py:60–67：顶层证据失去具体运行归属。** 文件名 `viewer_phase1_resources.jsonl`、`viewer_resources.jsonl`、其他 `*_resources.jsonl`、`*_launcher.log`、`geometry.json`、`pytest*.xml` 以及 `build_provenance/*` 不能由该prefix规则解析到真实command，被统一归为历史delivery。默认note却说阶段和状态可从关联run获得；这样查看STATUS中的单文件就找不到正确阶段，特别容易混淆viewer重启前后日志。最小修改：对顶层命名和build_provenance显式映射到真实run；旧viewer另附保留原字节的路径映射和SHA256。

**P2，prepare_delivery.py:89–101：COVERAGE子证据缺就近来源身份。** 顶层source_digest标最终b2c，但内嵌geometry来自144eb；tests只有计数，没有就近command来源；native和labels目录也可能包含不同源码阶段。commands总表虽然保留摘要，读者仍需自行猜测对应关系。最小修改：geometry、每份pytest、native、targeted_pairs和每组label目录附对应command_record、source_before/source_after与scope；不把目录存在当完成或通过。

export_review.py仅对ALLOWED和TEXT同增 `.cjs`、`.diff`，调用原Selection模型和pack；已逐段对照原bundle的路径、凭据、当前来源、资产、复制前后哈希、源变化、分卷大小与ZIP校验，未发现绕过。原snapshot不纳入tools的问题由source_supplement及显式3文件选择补充，但supplement只能作为另外的来源身份，不能声称原source digest已覆盖tools。

以上问题已告知主会话，子代理未改脚本。最终selection/归档映射尚未交付本审查，因此当前不签署最终打包来源完整通过结论。

补录证据 `provenance_final2.json` SHA256=`c553cbd9c2387f435da8a65ffae52c7d8618dac0162b3de8556de2950e815709`；包含本轮源码完整清单、实际pytest argv及前后摘要、JUnit统计、读取文件哈希、viewer_phase1归档文件哈希。

---

以下为保留的第一阶段审查原文，时间与适用源码范围不得外推：
# Cloud Update 来源与范围独立只读审查

独立审查会话：`/root/cloud_provenance_review`（主会话通过 collaboration.spawn_agent 委派的真实子代理会话；非主代理自评）。审查采样：2026-09-21 07:13–07:15 UTC。远程：SSH `4029`，项目 `/home/hdd3/zhanghaonan/projects/holocue`，本轮运行 `runs/simulation/cloud_update_20260921_ce64aff5`。只读取文件、计算哈希及读取现有进程环境；未运行测试/实验、未修改远程项目、未提交。

## 结论与适用范围

来源和已完成命令的记录可相互核对。独立调用原 Review Kit 的 `source_snapshot` 复算当前源码，得到 `bd938aafb0b6e056bfecb53aa88ca189ae43d3724489194e34bfe53bffc3be24`，与任务指定最终摘要一致；Git HEAD 仍为 `c4463b3a9842b3945ab7d1582ab8e49fcadca245`，表示旧提交加工作区变更，不应把旧 HEAD 称为最终源码身份。

1. Cloud Update ZIP SHA256 为 `ce64aff5e1d01a6a1a41068164e96f29352aa12830cc5ba8475820bc5dccc2e4`。独立检查包内 MANIFEST 列出的 **128/128** 文件，字节数和 SHA256 全部匹配。
2. 导入前固定清单列出的 **22/22 原 fixtures** 当前哈希不变。新 material_regions fixtures 未冒充原固定基线。
3. 从12个当前 scene.json 重新取得 **76个引用资产**；和导入前 execution.json 的 assets_before 独立对比，只有 BAY.glb、engine_bay/env/workstation.glb、BASKET.glb、BLUE.glb 四个预期资产变化，其余 **72个** 哈希不变。
4. engine_bay、shelf_picking、drone_bench 的3个新 build provenance 全部 source、asset、payload、blend、render 哈希与当前文件匹配，3条实际 build 执行记录 returncode=0。其余9个 scene.blend 在本轮没有新 build provenance，修改时间属2026-09-20，应作为历史构建产物。时间戳本身不证明历史构建正确性。
5. `pytest_final_command/execution.json` returncode=0，before/after 均为最终 bd938aaf 摘要；独立解析 `pytest_final.xml` 得到 **519 testcase、0 failure、0 error、0 skipped**。这是既有测试结果复核，没有冒称本审查重跑。

## 必须保留的证据边界

geometry、payload 和3个 scene build 都在 `144eb217ca914243fd631bdff095a55ed4ecd949f6d6cec2bc27fa48012f488d` 下执行，未在最终 bd938aaf 下重新构建/运行。两份完整源码清单的差异仅为 `src/holocue/annotations.py`、`src/holocue/viewer.py`、`tests/test_annotation_layout.py`。3个 build provenance 所列建模/构建输入当前哈希均仍相同，支持沿用这3个构建产物的来源，但不能把144eb217的geometry命令改写成bd938aaf重跑结果，也不能由此推导最终UI全部通过。

原 `source_snapshot` 仅覆盖指定源码目录、配置、scene.json 等，**不含 tools/**、GLB、blend、fixtures二进制和工作区辅助脚本。本报告额外独立散列 tools/gltf_validation 三个文件；资产和构建产物由独立清单核验。录制执行命令的完整 argv、摘要、开始/结束状态、所读文件和 SHA256 保存在随附 JSON。

## 尚未完成的实时验收

本次采样时 `labels_r2_command`、`live_text_command`、`bridge_blocks_command` 尚无 execution.json，只有 started.json；不能宣称本轮标签/文本/原生链路全验收通过。

- labels 首轮完整执行 returncode=1，stderr 保留 camera equivalence 断言失败：position_m误差24.927461309259602、aspect误差0.9。其 report 仅包含 blocks 完成的5种捕获；这不是整轮成功。
- labels_r2 的采样 report 仅包含 cnc_toolchange、connector，各自5种捕获，state_unchanged=true、model_request_executed=false。会话ID分别为 `9a193cdfdaaf4a50abfabac3ac7a4d5c`、`bd9bf5cd472044a78e96b300c84758aa`。只能记录这些已完成布局/镜头捕获，不代表任务规划模型验收。
- live_text 的采样 report 只有 optical_bench passed=true，会话 `880670426d0f487ba089e41173835331`。尚不能扩大到其他场景或全12场景。
- 原生 blocks 链路仍在运行，已读3个子阶段 resource_guard 日志均实际记录物理GPU2；本审查未将局部产物当作整场景或12场景完成。
- asset_import 首轮 returncode=1（changed数量断言失败）仍保留；后续 asset_verify returncode=0，且本审查独立验证实际4更新/72不变。应同时交付失败与后续验证记录，不删掉失败历史。

最终 selection 尚未提供；本版不为未查看的最终打包选择签署完整性结论。主会话交付 selection 后可追加核验。

## 资源与缓存

已读本轮顶层资源日志及 blocks 的3个原生子阶段资源日志：模型日志记录物理GPU1，原生日志记录物理GPU2，未观察到授权集合外GPU。vLLM PID 1777368 的实际环境为 `CUDA_VISIBLE_DEVICES=GPU-7ba69fc7-12ac-3dfb-8265-3476ce2504b6`，模型路径为项目内 models/Qwen3.5-4B；模型守卫 argv 为 `--gpus 1`，原生守卫 argv 为 `--gpus 2`。

抽样现存受检进程的 HF_HOME、XDG_CACHE_HOME、TMPDIR、PYTHONPYCACHEPREFIX、TORCH_HOME 全部指向项目 `.work/` 下路径。该结论针对已读取实际进程环境和日志，不是对所有第三方库缓存写入的全系统跟踪。

## 实际执行记录

| 命令目录 | 存在完成记录 | returncode | before摘要前缀 | after摘要前缀 |
|---|---|---|---|---|
| api_command | False |  | bd938aaf | — |
| asset_import_command | True | 1 | 144eb217 | 144eb217 |
| asset_verify_command | True | 0 | 144eb217 | 144eb217 |
| bridge_blocks_command | False |  | bd938aaf | — |
| build_drone_bench_command | True | 0 | 144eb217 | 144eb217 |
| build_engine_bay_command | True | 0 | 144eb217 | 144eb217 |
| build_shelf_picking_command | True | 0 | 144eb217 | 144eb217 |
| geometry_command | True | 0 | 144eb217 | 144eb217 |
| gpu_preflight_command | True | 0 | bd938aaf | bd938aaf |
| labels_command | True | 1 | bd938aaf | bd938aaf |
| labels_r2_command | False |  | bd938aaf | — |
| live_text_command | False |  | bd938aaf | — |
| model_command | False |  | bd938aaf | — |
| npm_install_command | True | 0 | 144eb217 | 144eb217 |
| payload_command | True | 0 | 144eb217 | 144eb217 |
| pytest_command | True | 0 | 144eb217 | 144eb217 |
| pytest_final_command | True | 0 | bd938aaf | bd938aaf |
| viewer_command | False |  | bd938aaf | — |

## 独立 tools 文件散列

| 文件 | SHA256 |
|---|---|
| tools/gltf_validation/package-lock.json | 4464fb72c7ee1fb3b44fe1747d91870ad71cdaca5639cd111958348e2d0adb96 |
| tools/gltf_validation/package.json | 2dcbbe578bb9103c6e2759d56745438f79204600719775e44b45adadc1e6a41e |
| tools/gltf_validation/validate.cjs | b38563db0f735453214b46b3dcfb1b37e5fd250f6cedcddd0efe1112f4b28394 |

## 12个 blend 来源身份

| 文件 | 本轮新build provenance | 当前SHA256 |
|---|---|---|
| scenes/blocks/scene.blend | False | 9045357d935d3e41a2941e7d937054d507e2efdeaca12635969ebe9f4efcc6a5 |
| scenes/cnc_toolchange/scene.blend | False | e1a5f4b4bfcf9843502582c6f071eba757456fd216c91ada03d18cd21ad7b945 |
| scenes/connector/scene.blend | False | d1b5d5b9b6a3beb7bc54cb70cf316a3e3725d0854c1f590380de9cc934f440c9 |
| scenes/control_panel/scene.blend | False | ef93a7d5d34a15892bb08113fc0b71085e58cee86431f58aa76077a18e00e22e |
| scenes/dig_site/scene.blend | False | 07c31ee77e48ab11203474f0b044bcb4442ca62a79305c9b0cbd47e0031a92e8 |
| scenes/dive_fillstation/scene.blend | False | bb80fd305f2a1a7b3bb6377bc84b8baae8c2a6095fd1cb446f0c1be071b90114 |
| scenes/drone_bench/scene.blend | True | da730c06202bb8a8f8dddb5bab234e78dbb3db72f671624167f19c61f7623093 |
| scenes/engine_bay/scene.blend | True | 1f8a6bf78f82fbcc2c9a64d27cb917d0e27c206e64d1d58f331a7dfd168a286f |
| scenes/infusion_ward/scene.blend | False | a301333fb16db1e3b65ab37844722df011295300e287397880cfcbb6ecac22f0 |
| scenes/optical_bench/scene.blend | False | a77bbf01c1008a35d6e21d48818bd60721e8079650a6b46e759d9d2b492f3c56 |
| scenes/server_rack/scene.blend | False | 711f8265601ecd6615f751fa923caab7e134bc3b7c3d2e50210d873b6b71c448 |
| scenes/shelf_picking/scene.blend | True | 608f8d6f15fc5ee756876874a8596e5d924dc3d9f3130f9f4e97126ed230e455 |

## 可复算材料和审查命令

- `provenance_audit.py`：本独立会话实际执行的只读审查程序，通过 PowerShell 管道将文本传入 SSH，不在远程写脚本。
- `provenance_audit.json`：source_snapshot完整清单、包检查、22固定fixture检查、76资产检查、3新build输入/产物核验、12blend当前哈希、实际command argv与状态、测试统计、资源日志汇总、实际进程环境、所有读取文件的SHA256/bytes。
- `provenance_supplement.json`：原生GPU2子阶段日志哈希和摘要，以及失败日志/预检原文与哈希。

可复算命令（从本地报告目录执行）：

```powershell
Get-Content -Raw -LiteralPath ./provenance_audit.py | ssh 4029 "cd /home/hdd3/zhanghaonan/projects/holocue && .venv-simulation/bin/python -B -"
```

程序调用 `review_bundle.py:source_snapshot(project)`；工具本体SHA256为 `65b69df894c346ab8d9684e156d6ed48a6387f4ea05e3b948c93a49253f6072c`。失败的初步环境探测（系统python不可用、系统python3无pydantic）未触发安装或改动，随后使用项目已有 `.venv-simulation/bin/python -B` 完成独立复算。

| 本地证据文件 | SHA256 |
|---|---|
| provenance_audit.py | ff1c2d3429f424ce2509b637501818aa291fe79c7d7c57fb12e5b2c5c38ea10b |
| provenance_audit.json | a0d6d3379fdca85873381fbd66ae1490362fba4bfd6d44adbdccdd7147baa5b1 |
| provenance_supplement.json | eedc9c829c433cf9bb546604d695913387a0ac9ad60282f89e1829343eb178a5 |
