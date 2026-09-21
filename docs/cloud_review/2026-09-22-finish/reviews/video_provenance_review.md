# 首场真实视频与最终选择器补录

**blocks首场真实采集与制作均已完成，来源及完整帧证据通过本轮只读复核。** 这只覆盖首场，不将另外11场或十二场合辑预先写为完成。未重跑实验、采集、转码或选择器，未修改工具。下方原静态审查作为历史记录保留。

实际session为`4d43c190d4b54583b9b14808d71a6728`。`video_blocks_01_command`、`produce_video_blocks_01_command`均rc0，源码before/after为c33e1ae4完整摘要，资产before/after为36866cf完整摘要。批次与单场manifest相等，capture前后来源与工具hash相同，单场身份亦吻合。

逐项读取13个UI阶段的snapshot/view/browser_capture与原PNG：session/revision/epoch全部一致，browser passed全部true，原图hash全部匹配。4张介绍原图亦hash一致、同session，初始queue/completed为空。final为idle且queue/suspended为空。events中两条plan_committed均为live `Qwen/Qwen3.5-4B`、HTTP200，并有非空raw_response和raw_http_body；同session `/api/v1/sessions/<sid>/events`实际API读取的body为JSON字符串，解码后与events.json完全相等。

| 实际媒体 | 字节数 | 时长 | SHA256 |
|---|---:|---:|---|
| 原始WebM | 30475829 | 424.08秒 | d380aba15cac9f1dc1fa2bb8b92743947e71a6e4819d35df82c7c5c062b5732e |
| workflow_realtime.mp4 | 20705401 | 424.08秒 | 29765483116de62328dbe09ba03221db955efdcf99b698cb46e6cf1b6726391c |
| scene_introduction.mp4 | 499278 | 24秒 | cb8cb3180002d0fd04ff22589e10ae5d9d1e59511e9737612733e10b5bd970bd |

三份媒体实际SHA256均匹配manifest，均小于47MiB，首场原始录像可以直接纳入既定分包策略。制作记录的ffmpeg/ffprobe均rc0。独立解析已保存的输入/输出全部解码帧记录，两者均10602帧，严格递增，首PTS均0，末PTS均424.04秒；逐帧相对PTS最大差为0，数量也与解码器nb_read_frames相等。未重新运行解码器，本核验依据真实制作产生的完整逐帧记录与媒体hash。介绍4页×6秒=24秒；本轮不替代视觉审查的逐画面检查。

## 合辑与选择器局部复核

- `combine_introductions.py` SHA256 `32e55e3e2029238d4fa738724f661e5c2553676c1c8aa1a62f0e0fc08075f373`：已修复目录名与manifest.scene_id未绑定、介绍路径可跨场复用的问题。现要求scene_id相等、输入限定对应produced目录；12段实际解码帧总和必须等于输出实际解码帧数，输入与输出保持25fps，合辑时长差不超过0.05秒。manifest输出多输入sources及outputs接口，与选择器一致。工具未执行，合辑仍待验。
- `prepare_delivery.py` SHA256 `18540b15995152b6988a8793c882aa0e1926261a5f7667a047f65dc295aa1722`：已修复合辑sidecar无capture owner而必然拒绝选择的问题，合辑整个精确目录映射真实combine命令；已修复继承native/assets被重分为reports，现保留原group。保留RUN2 sealed链、RUN3 write-once inventory和direct cleanup独立身份，RUN4命令严格双侧source/assets匹配，按实际argv映射capture/produce，显式派生关系与UI-only coverage符合原strict schema。
- 两个新helper仅AST解析。选择器对照首场实际manifest字段、完整帧证明文件名及已读取历史coverage层级兼容；未执行选择器，也未声称实际成员集合验证完成。执行后仍需核12场精确集合、失败attempt保留、RUN3冻结清单及最终ZIP成员。

读文件列表及哈希、实际命令、帧核验结果记录在邻接JSON的`blocks_actual_capture`、`blocks_actual_production`、`selector_and_combiner_static`，先前发现与闭合状态一并保留。

---

# RUN4 视频来源与选择器静态审查

审查会话：`/root/cloud_provenance_review`；RUN：`cloud_finish90_20260921_e67b574`。本轮只读检查两份视频工具、继承的工作流断言及原 review_bundle schema，未启动采集、转码、实验或选择器。RUN3 审查记录保持冻结。

**当前结论：已发现的两项来源/失败标记问题均已修复，静态复核未发现仍阻碍试运行的缺陷。实际十二场视频完成、画面可读性、最终选择和包成员仍待验。** 这不是十二场视频或原生验收通过的结论。

## 已核工具身份与修复

| 文件 | SHA256 |
|---|---|
| capture_ui_videos.py | 25aec6849ceb5276ce44979ee38add33c71ddfda11af678f1a3d298514c0442e |
| produce_videos.py | 612db26fbe8f52ef1168d725ced5e762ce841af007ebced0773d1ed3dbeccefe |
| README.md | 9c9ad77b2fe2ce9ba071bd0455be4260761b6611323fb7524ff8e670800f4121 |

本地与4029同名文件大小/hash一致，两个Python文件AST解析通过；未导入执行它们。

- 原P2：workflow已返回passed=true之后，最后页面操作异常只更新error，可能保持成功。capture工具219–225行现明确重置passed=false，并以workflow_assertions_passed_before_failure保留先前断言事实；已闭合。
- 原P2：制作时只有批次before/after快照比较，单场身份未与其绑定。produce工具163–167行现逐场要求source_digest、asset_digest、capture_script_sha256均等于批次before；批次before/after先行相等检查；已闭合。
- 动态加载review_bundle前已注册sys.modules，兼容其模型定义。制作工具不再仅比较容器时长：实际解码输入/输出所有帧，检查数量完全相同、所有相对PTS误差不超过2ms、首尾记录与容器时长。最后包时长可容许一帧区间差异，不能将这一容差扩大为允许丢帧。

## 证据能证明什么

VideoAudit继承原Audit.workflow，仍执行真实初始指令、临时检查与恢复、确认完成、最终队列/状态和对象位姿断言；继承代码617–620行要求至少两条live plan_committed及非空raw_response。仅替换capture、object_views与exporter机制，因此是UI-only证据，不启动Blender，不替代native双路捕获。成功与失败均保留真实会话及事件；失败不能制作“完整流程”。

WebM从新浏览器页面开始录制，包含介绍采集、完整真实模型等待、暂停/恢复/确认和页面操作。上下文close后才读取路径和hash。原workflow可见动作播放倍率仍为0.1；“等速”指对这份真实录像1.0倍转码，不声称动作本身采用1.0播放倍率。MP4仅在整页下方加说明，代码无裁切、拼接或加速完整流程。

介绍片明确是新会话、提交指令前真实Viser截图的幻灯片；标题/说明由scene契约生成，最多3个关键对象detail，加全景。不是连续物体运动录像。最终仍应逐场复核其实际MP4解码、页数×每页秒数、字幕与所存contract对应；当前脚本对介绍片记录ffprobe而未做同等逐帧完整性证明。

全帧数量/PTS证明转码时间线，不能独自证明画面无黑屏、字幕可读或内容正确。最终需查看实际视频。中断时若进程被杀而未写provenance_after或未flush WebM，该attempt仍是失败/未完成，不能靠已有部分文件升级为成功。`.work`不属于旧source_snapshot范围，工具文件与运行hash必须独立入选；运行期间冻结工具，若后续修订应保留所执行版本，而非只交最新文件。

## RUN4 选择器具体建议

1. **两种继承身份分开。** RUN2有已封存21ZIP：继续核published UPLOAD_INDEX中的00ZIP大小/hash，从`HoloCue_Review/MANIFEST.json`逐个核继承路径大小/hash。RUN3没有新ZIP，只能称preserved batch；固定其selection、coverage和新增证据inventory及hash，读取时逐项验证。建议RUN3 run_id使用previous90_前缀，保留RUN2内部sealed_历史层级，避免重名或把全部历史提升为current。
2. **保留RUN3全部实际范围。** connector14、control11、dig18各自passed/rc0；dive12局部capture但无整场report/rc1；guard15项在c33运行；多guard实际低于25.154539 GiB；guarded shutdown预检rc1和direct cleanup/verify各rc0分开。直接清理是独立historical/recorded证据owner，不能把service_shutdown/owned_process_verification错误归到未实际执行清理的shutdown命令。62个退出身份及清理端口/GPU快照均入选。旧519、geometry/build、labels、blocks/CNC继续保留其原阶段身份。
3. **RUN4命令严格来源。** current判定要求source_before==source_after==最终source，并且assets_before==assets_after==最终assets。实际返回码保留；服务关闭、守卫拒绝与实验成功分别说明。source_final/assets_final只描述导出时状态，不冒称全部历史均在该源码执行。选择器、导出目录及其自身命令应按既有规则排除递归。
4. **按视频attempt映射owner。** 新目录videos不能沿旧递归逻辑统一落到delivery。每场capture与produce有各自真实执行记录；WebM、页面原PNG、snapshot/view、timeline、events/raw_response归capture；成片、完整解码JSON、frame_timing_verification、ffmpeg命令日志归produce。失败attempt保留原失败，另一个成功attempt不可覆盖它。
5. **严格schema。** Run.scope只有current/historical，status只有原schema枚举；UI-only写note与COVERAGE独立分项，不加schema禁止的字段、不计入native阶段数。Evidence只有既定reports/visuals/assets/native组。workflow MP4的derived_from指实际raw WebM，derivation_command_record指实际produce execution；介绍多图来源用introduction.json及produced manifest完整列举，可将derived_from指该介绍清单，所有原图同时入选。
6. **最终精确集合。** 以实际list_scenes的12个scene_id为权威，核12份成功raw WebM、12份workflow MP4、12份intro MP4，每场均有真实session、前后source/assets快照、工具hash、契约hash、原始模型回复、capture证据和制作/解码证明。未完成、未运行和成功分列，不用文件数量代替会话匹配。RAW超过47MiB时应使选择失败并明确解决原录像交付；不能复用旧大视频逻辑静默只交派生片，却声称原WebM已交。

本轮读取路径、hash、代码范围和实际静态检查记录在邻接`video_provenance_review.json`。后续仅需针对真实产物、最终选择器和ZIP复查；本报告不预先认定其通过。
