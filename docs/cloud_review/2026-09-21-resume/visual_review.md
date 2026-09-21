# HoloCue resumed batch independent visual review

CNC 本批 18 个已保存阶段的 36 张原生配对原图已由本独立会话实际打开查看。未发现这些静帧中主要几何或提示位置的 Viser/Blender 不一致，工作区六标签可辨认；接收孔近景低视角和 ghost 上部裁切仍是未解决的视觉限制。主线程报告 CNC 18 阶段运行检查全部 passed；运行通过与下述视觉限制分别成立，不能据此声称所有细节或全部场景视觉验收通过。

独立审查会话：/root/cloud_visual_review。RUN：runs/simulation/cloud_resume_20260921_ea8c2f7。主线程提供 HEAD ea8c2f7、最终 source SHA-256 37b81f92c4bb91b5ca68180be99b1f1810b40657842cf2d3145bd1eeb8d3f0fe，并已独立核对 103 个资产/fixture 与封存批一致；应用/资产与 b2c379ba 版本相同。本图像审查不冒充另一份源码或资产审计。

## 实际查看范围与方法

从已完成目录下载 PNG，以 tools.view_image 实际查看每张原图。共 18 阶段 × 2 原图 = 36 张；包含先前本批已看 4 张，本次增加 32 张。未计旧批 76 张，未以测试通过、缩略图或抽样帧代替其他对象。每图相对路径及 SHA-256 见 visual_review_manifest.json；清单中 viewed_original=true 仅表示实际查看。

所有阶段位于 bridge_batches/cnc_toolchange/cnc_toolchange/，每阶段均查看 viser.png 与 frame_0000.png：

|阶段|实际视觉结论|
|---|---|
|01_start_paused|框架、面板、刀库、承座及两刀柄可辨；六标签完整，配对几何及提示一致。|
|02_middle_paused|工作区及标签完整；旋转/检查提示在两端位置一致。|
|03_temporary_inspection|T03 颈部与顶端清楚，青色环围绕目标；两端匹配。|
|04_original_restored|旋钮正面、垂直指示线及完整环形箭头清楚；特写无工作区标签。|
|05_endpoint_waiting|旋钮环形箭头完整入画；指示线对比偏低但可辨，两端位置一致。此时只是该步骤等待确认。|
|06_final_workspace|界面显示计划完成；T09 已在 POCKET9 中，原左前位置空出；T03 保留右侧。六标签完整、可区分，两端几何一致。|
|step_01_start|T09 原位及装入提示清楚；工作区标签完整；两端相符。|
|step_01_middle|移动中 ghost 位于主轴/刀库前，实体 T09 仍在原位；提示及场景配对一致，六标签完整。|
|step_01_endpoint|ghost 到承座上方，实体仍在原位等待确认；全景中 ghost 完整入画，两端一致。|
|step_01_endpoint_receiver|承座正侧面占主画面，孔口近乎侧视，不能看清内孔；ghost 上部被画面顶边裁切。两端同样受限。|
|step_02_inspection|T03 拉钉颈部、顶端轮廓清楚；青色大环围绕目标并略压到下部锥体，未遮住主要检查处；两端匹配。|
|object_MODESWITCH_detail|完成后的旋钮侧面、齿纹与向右指示线可辨；两端匹配。|
|object_PANEL_detail|PANEL / TRAINING READY、四按钮完整；Viser 较暗，Blender 更亮，结构一致。|
|object_MAG_detail|环形刀库、孔沿和中心结构可辨；左部被主轴遮挡，两端一致，不能宣称全部内部细节可见。|
|object_POCKET9_detail|界面已显示接收 T09，为占用后承座；低视角仍不能核验空孔内部，上方实体 T09 被裁切。|
|object_T09_detail|已装入 T09 的颈部、锥体、法兰及与承座关系清楚；承座下部被画面底边裁切。|
|object_T03_detail|独立 T03 刀柄主体、颈部、法兰和下柄完整可辨；两端一致。|
|object_T03_inspection|无提示遮挡的拉钉颈部及顶端轮廓清楚；下部锥体因检查特写裁切；两端一致。|

Blender 的材质、照明较浅且柔和，Viser 更暗；Blender 原生图不含 Viser 标签和 UI，此差异不是缺失标签。工作区部分引线被场景几何遮挡；没有观察到工作区标签文字裁切或重叠。这里的“一致”限于已保存静帧的目视几何、对象和提示位置，不是像素等同或视频连续性结论。

## 保留问题与证据边界

- 接收孔 / ghost 视角限制未解决：step_01_endpoint_receiver 不能显示孔内，ghost 上部裁切；object_POCKET9_detail 是已占用状态，同样低视角且上方 T09 被裁切。全景 endpoint 中 ghost 完整、最终装入位置可见，不能据此替代空孔内部检查。本批没有 object_POCKET9_inspection 目录，不宣称该检查已覆盖。
- P3 引线可见性限制保留：部分连接线在框架/场景几何处消失。此前 blocks B 间隔问题仍保留在历史报告；源码分析指出端点与标签 world_position 相同，深度遮挡只是可能原因，不能写成已经证实的 anchor 算法错位。本次未修改渲染器、相机、资产或任何参数。
- T03 检查部位在本次两种 inspection 原图中清楚；这补充了此前未完成检查的可见性证据，但不证明全部物理内部结构正确。
- 仅审查这 36 张静帧；没有逐帧观看所有视频，也没有把 CNC 覆盖外推到其他场景。

05_endpoint_waiting 的已完成 snapshot.json、view_state.json、browser_capture.json 也曾只读保存核对：selected_id=MODESWITCH、view_mode=detail、revision=13、epoch=11、execution=paused、clock_advancing=false；当前 cue elapsed=3.261119283793956 秒、duration=3.0 秒，T09 插入和 T03 检查当时仍在后续队列。两次真实 canvas 哈希一致、尺寸 1276×1000 是捕获稳定性的辅助证据，与实际看图和最终完成阶段分别记录。

## 本批停止与未运行范围

主线程通知：CNC 18 阶段全部 passed；随后 connector 因模型服务被真实主机内存守卫停止而 0 stage 失败，其余计划场景未运行，三组 changed_pairs 也未运行。此处运行结论来自主线程汇总，精确守卫值及运行报告由主线程随批次打包；本图像审查不补造 connector 图片或把未运行项改写为通过。审查仅读取完成文件，没有实验、浏览器或服务操作；不等待后续新图。

## 历史来源（不并入本批计数）

旧批独立审查共 76 图，报告和清单位于 ../cloud_update_20260921/visual_review.md 与 ../cloud_update_20260921/visual_review_manifest.json。其中包括最终 12 场景宽/窄标签审阅、旧批原生局部与资源停止限制，以及明确标记为 c4463b3 历史来源的 optical_bench/server_rack 全景。此次未重新下载或累计这些旧图，未改旧报告和 ZIP。历史资料仅为已审依据，不能当本次新原生运行结果。
