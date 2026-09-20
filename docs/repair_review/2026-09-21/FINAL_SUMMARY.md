# HoloCue 定向修复与审阅资料

日期：2026-09-21。项目位于 4029 的 `/home/hdd3/zhanghaonan/projects/holocue`。本批按 `HoloCue_Repair_Review_Kit_20260920.zip` 执行定向修复，原始仓库基准为 `55cfe656182411965d0f12d8a5ff92b2d885535f`。完整十二场景 199 阶段原生验收未纳入本批；逐场景实际状态见 `COVERAGE.json`。

## 已完成修改与验证

- 三处手写读取已替换：GLB 顶点法线使用 Trimesh 公共读取接口，材质和纹理元数据使用 pygltflib，模型分片使用 Safetensors `safe_open`。真实模型目录验证了两个分片、738 个张量。几何、实际导出法线、材质、纹理、分片索引等检查保留。
- 保留已合并的 CLAMP、L1/L2 和其他建模修复。`modeling.py` SHA256 为 `0a7bdcb1e06ede04fb4fcd4689a25aa5cce9a4e347fe68420dffd0c9130837aa`。22 份固定 fixture 的原始字节与批次开始时一致。
- 光学场景通过 Viser 官方 `environment_wxyz` 配置固定环境方向 `[0.594394087626887, 0.1712372678360988, -0.2126979877009283, 0.7563947598484568]`，保持 studio 环境、强度 0.1、M 金属度 0.95 和粗糙度 0.08。其余场景保持默认环境方向。
- 标准构建入口完成 76 个 GLB、十二份 payload、十二个 `.blend` 和十二张 Blender 原生全景。顺序为 GLB、payload、Blender；逐场景保存输入、源码和实际输出哈希。构建后独立核验了全部记录。
- 完整 pytest：431 项通过，854 条警告，330.41 秒。其中相关联合几何回归 89 项。十八条有序动作路径全部完成，协议保持每对象 1536 个表面采样点、seed 4701、41 个时刻、0.75 毫米阈值；采样结果未出现超阈值穿入。此结论只覆盖上述有限采样。
- 十二场景真实本地 Qwen3.5-4B 流程通过，包含 30 个有序步骤，保存全部原始请求、回复和任务状态。GPU 1 运行原有模型配置；GPU 2 用于同会话原生渲染。未变更模型、上下文长度、批次设置和几何协议。
- 实际 Viser 页面亮度、焦点检查通过，画布分别有 3256 和 367 个像素变化；N 与 sigma 检查分别有 76050 和 351288 个像素变化。这些数值是全画布差异计数，不能用来证明变化的空间局部性。
- 主页面保存了十二场景全景和八张支撑特写，捕获前后任务状态一致。独立视觉审阅记录了实际查看的原图，详见 `visual_review.md`。
- 四个重点场景原生同会话检查全部通过，共 63 个阶段：engine_bay 18、optical_bench 17、server_rack 14、shelf_picking 14。各场景均执行原脚本完整流程，保存 Viser/Blender 配对原图、接收端视图、对象特写、版本/实体位姿/相机断言、输入帧和完整录屏。
- 真实独立代码、视觉、来源审阅分别由 `/root/repair_code_review`、`/root/repair_visual_review`、`/root/repair_provenance_review` 完成。视觉代理实际查看 63 张原图；没有完整观看长录像，没有将清单之外的图片声称已经查看。

## 镜面证据的准确范围

`mirror/` 保存本批真实 optical_bench 会话 `27dd392ce52445b8b5a850b24f513c12` 的初始状态与旋转完成状态。受控配对采用生产 `SceneRenderer`、官方 Viser 客户端和不可变真实会话快照；每种环境方向使用新客户端。相机、实体位姿、材质和环境强度保持一致，关闭提示的条件保持一致。该配对使用独立显示检查入口；主页面交互证据另见 `viewer_response/` 和 `bridge/`。

实际 HDR 下载内容、身份、相机、材质、客户端环境参数和七张原始截图均保留。studio HDR JPEG SHA256 为 `e03b8f898562515714bab61fee0dd1e09c880e7b06c979148fc1eaca52680b7a`。调整后初始与完成姿态的镜面均可见；初始姿态右侧仍有暗带，记录为实际环境反射。

早期 `mirror_prebuild*` 属于开发材料。初次热更新未产生可见改善，r2 相机一致性断言失败，r3 固定方向仍偏暗，r4 使用早期会话验证最终方向。它们保留原记录，单独归入 historical；最终通过依据为当前 `mirror/`。

## 网页端继续审阅的位置

1. `code_review.md` 中的 P3：成熟 GLB 读取库未保留旧实现对“头部声明总长度严格等于文件长度”和“禁止 sparse accessor”的显式检查。当前实际资产及几何、法线、材质、纹理检查通过；这两项格式边界检查仍缺失，不能声称所有旧断言完全等价保留。
2. `visual_review.md` 中的 P3：POST2 标签与 L1 正面下部重叠；L2 标签投影到后方 TARGET 区域。镜片、镜架和目标标记仍可辨，标签位置未在本批额外修改。
3. `support_views/dig_site/FLAG.png` 缺少足够接触深度线索，单张截图不能确认入土深度。BOTTLE3 特写补足全景中的编号遮挡，但部分后方固定点仍不在视线内。
4. 光学响应保持 `analytic-gaussian-preview-v1` 解析仿真。真实光学标定、连续运动完整碰撞证明、全场景近距离游戏级视觉认定均未由本批证据建立。
5. 发动机场景 `object_CLAMP_detail/viser.png` 左下箍带下方出现局部细碎条纹和三角形边缘；Blender 同区也有暗部与局部三角边缘。原图无法确定根因，具体修正留待后续定位。
6. `step_01_endpoint_receiver/` 的青色提示覆盖接收孔区域；最终 `object_PLUGPORT_detail/` 已有火花塞占用，只能看到浅色圆面与暗环。终点图无法证明空孔内部及孔壁深度；空孔几何文件与独立几何检查另外保留。连接器检查面的四个端子和 REAR KEY + CONTACTS 标识在 Viser、Blender 两路均可辨。
7. 完成装配后，光学对象侧栏仍使用“待装镜架 L1”标题，与 idle 完成状态的表达不一致，列为 P3。完成状态图中 L1 与 POST2 套筒、L2 与套筒及方座的外部衔接可辨；主页面 M 的镜面、边框、刻度和黄色指针可辨。内部接触和配合精度仍由独立几何记录限定。
8. 机柜 SLOT4 与 SPARE 标签重叠，槽位完成占用后仍显示“四号空槽位”，列为 P3。rev13 的终点预览保持实体原位并显示终点提示；rev16 的完成确认提交实体位姿，SPARE 位于 SLOT4 导轨之间。这一状态差异符合当前确认流程。NODE3 背面连接器和圆环可辨，截图不能确认内部深度。
9. 货架 `05_endpoint_receiver/frame_0000.png` 的篮筐前底边和 `03_temporary_inspection/frame_0000.png` 的 BLUE 箱体底边出现局部深色斜纹、三角片状明暗，Viser 对应区域更均匀，列为 P3。箱体轮廓与 BLUE SHIPMENT 027 文字仍可辨；原图不足以确认根因。

## 来源与交付

本批运行目录为 `runs/simulation/repair_review_20260920_25bcc909`。源码和资产分别使用 `sha256-path-size-content-v1`：

- 源码：`2ef99b6626387225afacc10502e6d3b83e1359a0c7e528d7036e54f683002366`。
- 资产：`1926ec8e7f696dd3565ce016f144f640c630c6d305441062921c5e18efc1280d`。

命令包装器位于资源守卫外层，保存 started、execution、标准输出、标准错误、真实返回码、执行前后源码与资产摘要。资源守卫保留主机内存 50.30907897949219 GiB，使用项目内部缓存，仅管理本次记录的进程。服务停止详情见 `service_shutdown.json`。

每份上传 ZIP 独立解压至同一目录组成 `HoloCue_Review`。优先上传 `00_review_index.zip`、全部 `01_source_reports_*.zip` 与 `UPLOAD_INDEX.json`，再上传全部 visuals、assets、native ZIP。具体文件与校验值见 `UPLOAD_INDEX.json` 和 `SHA256SUMS`。源代码、实际 GLB、固定 fixture、原图、原始模型回复和选定原生文件均以内容交付。

原生分层渲染的中间 EXR 保留在服务器 `bridge/<scene>/<stage>/frame_0000_passes/`。上传包选择最终原始 PNG、分层 manifest、输入状态和核验报告；完整中间 EXR 未纳入上传选择。数据库、模型权重、认证配置和缓存未纳入资料包。

完整录屏包含各阶段暂停等待离线 Blender 渲染的时间，不能作为人工任务耗时或页面交互延迟的测量。超过分包限制的录屏提供有来源记录的 H.264 审阅副本，保持原始尺寸、帧率、起点、解码帧数和完整时长；原始 WebM 继续保存在服务器，副本报告保存两者哈希及实际 FFmpeg 命令。

本批模型、API、Viser 三项服务已依据 PID 与创建时间核对所属关系后发送 SIGINT，停止记录中没有剩余所属进程。最终端口与 GPU 状态见 `evidence_verification.json`，独立来源审查边界见 `provenance_review.md`。

原生同会话 ID：engine_bay `8d785de4cc254864898a3e9b36d862ae`；optical_bench `b7223966e6404e54965ea84c8213047e`；server_rack `6a7aba935a8e421880ec9fa8c4bde696`；shelf_picking `138cf71929bb4ba2919b397b46da242a`。货架 RED 完成位姿为 `[-0.25, -0.62, 0.905]`，最终两路工作区图可见 RED 位于 BASKET 内。

其余八场景的完整原生交互脚本、十二场景 199 阶段总验收、本批之外的双客户端/重启/恢复专项未重新运行；相关旧记录保持历史归属。真实光学硬件仍未参与本批验证。上述未运行项和本报告列出的 P3 均保持未完成状态。

独立来源审查发现首份选择草稿遗漏 `acceptance_20260919_1706` 历史报告。最终选择已加入独立 `historical/recorded` run，原样导出旧验收准备稿、源码摘要、覆盖与缺失阶段说明，以及已有的原生、模型、页面、响应、故障和 pytest 报告。历史资源事故及无效 GPU 0 试验报告也保留历史归属；它们不属于本批 GPU 1/2 执行。没有改写旧报告的日期、状态或算法摘要。

代码与十二场景资产已拆分为 17 个提交并推送，截止 `9f1f896ed207dd03aa7dbab9601f3b8d563b2cef`。首次推送发生 SSH broken pipe，实际命令返回码 128；保留失败日志，使用连接保活的后续推送返回码 0。最终报告另作一个提交；其提交号与推送结果保存在 `report_commit.json`、`push_docs_command/execution.json` 和本地交付回执，避免文档内自引用提交哈希。
