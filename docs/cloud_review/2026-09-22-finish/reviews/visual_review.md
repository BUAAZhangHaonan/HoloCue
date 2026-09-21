# HoloCue RUN4 独立视觉审查（定稿）

本批实际查看 179 张来源原始 PNG（按唯一路径去重）、251 张视频代表帧和 8 张审阅副本对照帧，共 438 张不同路径 PNG。12 场景最终采用的 24 个 MP4 共覆盖 234 张代表帧，在所审范围内可接受并保留本文限制；另保留旧 connector attempt01 的 2 个 MP4/17 帧 P2 整体漂白拒绝证据。完整原生流程 124 图来自 DIVE 46、Drone 40、Infusion 38；定向配对成功 14 图（Engine 4、Dig 2、新 Shelf attempt03 8），旧 Shelf 失败尝试前两阶段 4 图另列；相机局部回归 21 图、显示响应 7 图、额外显示排查/对照唯一原图 9 张另列。分类和逐图 SHA 见各 manifest 与 final_review_inventory.json。相同画面在不同捕获阶段仍按不同来源路径记录，不把它们称为不同视觉内容。历史封存不修改；代表帧审查不等同全视频逐帧人工通过。

独立会话 /root/cloud_visual_review；RUN runs/simulation/cloud_finish90_20260921_e67b574，HEAD 按批名 e67b574；主线程提供 source SHA-256 c33e1ae4cdd7251c217e61caa31a2d58668984b0db6653d1fe4ac29929862e2a、asset SHA-256 36866cf33627a522897a66a3e1247587608d72959dc792d029de0136a0b78af8；本会话不将该来源通知冒充独立源码/资产审计。所有新图只读下载并以 tools.view_image 实际打开，逐图 SHA 与查看标识见 visual_review_manifest.json。首轮 stages 快照另存 dive_fillstation_stages_initial.json。

## dive_fillstation 首轮原图

路径前缀 bridge_batches/dive_fillstation/dive_fillstation/。下表每行均实际查看 viser.png 和 frame_0000.png 两张：

|阶段|实际视觉观察|
|---|---|
|01_start_paused|七个工作区标签 GAUGES/STEM/BOTTLE1/BOTTLE2/VALVE/BOTTLE3/QRC 完整分离，主要设备入画。BOTTLE3 被前方台面和支架部分遮挡但可辨；两端几何与提示相符。|
|02_middle_paused|全景标签与设备可辨，任务面板显示 BOTTLE3 检查、QRC 接入、STEM 旋转和 GAUGES 提示队列；两端位置一致。|
|03_temporary_inspection|BOTTLE2 的 TRAINING BOTTLE2 字牌清楚完整，青环完整入画；瓶体下部和顶部小部分出边，属于局部检查视图。|
|04_original_restored|恢复 BOTTLE3 字牌检查，文字及检查环完整，两端同一部位；瓶体下部裁切。|
|05_endpoint_waiting|BOTTLE3 检查字牌和环完整，原任务队列已恢复；面板输入仍为临时 BOTTLE2 指令，不据输入栏误判当前检查目标。|
|step_01_start|QRC ghost 在支台原位附近，七标签完整，两端一致。|
|step_01_middle|QRC ghost 沿接入方向移动，实体留在支台；工作区标签和设备清楚，两端提示位置一致。|
|step_01_endpoint|ghost 位于 VALVE 接收口，实体尚在原位；不能把 ghost 到位当确认后装入。|
|step_01_endpoint_receiver|VALVE 圆形口缘和部分内壁可见，侧圆盖完整。ghost 覆盖孔口并伸出左边界，Blender 内部对比更低；不是无遮挡完整孔内检查证据。|

工作区未见标签文字缺失或明显错误指向；native 两端几何、目标及提示位置目视相符。Blender 光照更浅、更柔，不包含 Viser UI/文字标签，不能按 UI 标签缺失判错。保留接收孔 ghost 遮挡/裁切、瓶体局部特写裁切及 BOTTLE3 支架遮挡的实际限制。历史 P3 引线局部遮挡仍保留；未证明 anchor 算法错位。

## 视频与未完范围

当前视频实际范围以上述最新统计与 video_review_manifest.json 为准；后文各批阶段统计保留各次追加时点。DIVE、Drone、Infusion 本批原生和指定三组定向 pairs 的最终实际范围见本报告开头及末节。尚未实际打开的成片和运行中文件不算视觉通过。历史 cloud_update 76 图、cloud_resume 36 图、cloud_continue90 110 图单独封存，不混入本批新增计数。


## blocks 首场视频：4 页介绍与 11 个实时演示代表帧

来源 videos/blocks_attempt01/blocks/produced/，session 4d43c190d4b54583b9b14808d71a6728。两 MP4 已下载，实算 SHA 与制作 manifest 一致：intro cb8cb3180002d0fd04ff22589e10ae5d9d1e59511e9737612733e10b5bd970bd；workflow 29765483116de62328dbe09ba03221db955efdcf99b698cb46e6cf1b6726391c。source/asset 与本文来源一致。时间点与帧 SHA 单列 video_review_manifest.json，不并入 native 原图清单。

介绍视频 24 秒，每页 6 秒；实际打开 1/7/13/19 秒的四页。第一页面为工作区，后面依次为 A、BASE、B 特写。标题、对象介绍与整句任务均完整可读，自动换行后未出下方字幕区。页面顶部 1600×1000 区域保留完整右侧 UI 和左下坐标轴，字幕位于新增的下方 240 像素区域，所看帧没有覆盖或裁切原页面。A 的八凸点、BASE 阵列和 B 主体均清楚。B 页介绍写明底部结构可从检查视图观察，当前页实际为顶部特写，不误记该页已展示底部；底部由后述 workflow 帧补充。B 引线末段间隔仍可见，保留旧 P3 限制。

workflow 424.08 秒。已读取制作 manifest 与 frame_timing_verification：输入/输出均 10602 帧、全部相对 PTS 比较误差 0、duration 一致，verification passed。这是工具记录的时序核验，本会话没有自行重跑全片解码，也不把它冒充人工逐帧观看。

|实际打开时间（秒）|代表内容与观察|
|---|---|
|1|页面仍为白色加载页，底部标题与任务字幕完整；如实保留加载阶段，不据此认定转码丢页面。|
|40|完整工作区和右侧观察面板出现，A/BASE/B 标签可辨；字幕不遮页面。|
|130|初始任务暂停，右侧列出 A 装配和 B 底部检查；A 原位 cyan 提示可见。|
|167|A ghost 在路径中，实体仍原位，任务面板完整可读。|
|194|临时 B 底部检查，三个套筒和开口外框可辨，青环部分覆盖左右孔缘；右侧可读原计划挂起与恢复说明。|
|222|回到原 A 装配队列，ghost 位于路径中，原计划恢复可读。|
|262|ghost 到 BASE 上目标区域，原位 A 仍在，显示等待/暂停。|
|291|BASE 接收区特写，ghost 与底板凸点对应，右侧两步任务仍在。|
|338|页面显示当前计划完成，A 已在 BASE、原位空出，三工作区标签可见。|
|391|无提示环的 B 底部三个套筒和开口外框完整清楚，页面仍显示计划完成。|
|423|末尾 A 位于 BASE 的特写与完成状态可见；右侧 UI 和字幕完整，未观察到字幕出边。|

结论限于这 15 个实际打开帧：字幕完整、文字可读、原页面未被新增字幕覆盖或转码裁切，关键状态变化有代表帧证据。工作区 B 引线部分缺口与临时检查青环覆盖局部几何仍保留，不因成片而撤回。没有观看全部 10602 个视频帧、未检查音轨，不把首场代表帧检查推广到其余 11 场或 native Blender 通过。

## DIVE 完整场景补审：新增 14 阶段 28 图，累计原生 46 图

已只读下载最终 bridge_batches/dive_fillstation/report.json 与 stages.json；报告 passed=true、23 stages、browser_errors=[]。首轮 9 阶段 18 图不重复查看或计数，本轮将其余 14 阶段 28 张原图逐张打开。下表各阶段均实际查看 viser.png / frame_0000.png，来源沿用 RUN4 c33 source、36866 asset；不借用 RUN3 同名图片。

|新增阶段|实际视觉观察|
|---|---|
|step_02_start|竖直红色 STEM 拨杆与轴心完整，环形旋转箭头可辨；左右管道出边属于特写范围，两端一致。|
|step_02_middle|拨杆实体仍竖直，箭头推进并被主体局部遮挡；提示方向可辨，两端一致。|
|step_02_endpoint|提示到终点，实体仍竖直，等待确认状态；不能把提示到位当作实体已旋转。|
|06_final_workspace|UI 显示计划完成，QRC 已接到 VALVE、原支台空出，STEM 实体转为水平；七标签完整分离，目标与最终几何两端一致。|
|object_QRC_detail|QRC 的 DRY 字牌、完整筒身、防滑筋与 VALVE 接合外观清楚，无 ghost；内部接触深度不可见。|
|object_VALVE_detail|VALVE 方壳、侧圆盖和已接入 QRC 的接口关系清楚；QRC 外端出左边，开口已被接头占用，不能替代无遮挡空孔检查。|
|object_BOTTLE3_detail|BOTTLE3 瓶体、前字牌及底座完整清楚，支架在右侧，避免了工作区的主要瓶体遮挡；上部另属 QRC/VALVE 的几何局部出顶边。|
|object_BOTTLE3_inspection|无提示环的 TRAINING BOTTLE3 后字牌完整可读，周围瓶体上下出边，检查文字未裁切。|
|object_BOTTLE1_detail|BOTTLE1 全瓶、前字牌、底座完整；邻近 BOTTLE2 的底部部分出边，不是所选主体缺失。|
|object_BOTTLE1_inspection|TRAINING BOTTLE1 后字牌清楚完整，瓶体上下出边，目标字牌无裁切。|
|object_BOTTLE2_detail|BOTTLE2 全瓶、前字牌和底座完整；邻近 BOTTLE3 仍被支架挡住，所选 BOTTLE2 不受挡。|
|object_BOTTLE2_inspection|TRAINING BOTTLE2 后字牌清楚完整，瓶体上下出边，目标文字无裁切。|
|object_STEM_detail|确认后的红色水平拨杆、轴帽与连接部完整清楚，静帧能辨朝向已改变；没有做精确 90 度角度量测。|
|object_GAUGES_detail|三个圆仪表、刻线与指针全部入画且可辨，两端指针朝向一致；没有数值刻度，不能据图读出具体压力值。|

整场图像范围已闭合：23 阶段、46 张唯一原图。完成状态、接头最终位置、拨杆最终朝向与各对象目标细节可辨，未见新增标签缺失或明显错误指向。仍保留终点接收图的 ghost 孔口覆盖与左裁切、接头装入后孔内不可见、若干局部特写裁切与工作区 BOTTLE3 支架遮挡；后者在 BOTTLE3 自身 detail 中有无遮挡主体补充，但不抹去工作区局限。

其他任务状态仅按主线程通知记录：drone 仅 2 个阶段后失败，engine UI attempt01 失败并保存 16 阶段，不记完整通过，失败证据保留。本会话未审这些失败图。CNC UI capture 已完成 18 阶段；本次只审已完成 produced_attempt02 成片，见后节，不复用旧 produced 中的部分文件。后续 resume01 的成功不能倒写前述失败。RUN3 旧封存未改动。

## CNC 视频补审：制作版本 641b7，新增 17 张代表帧

来源 videos/cnc_toolchange_attempt01/cnc_toolchange/produced_attempt02/，session b25f0b9ee42842279957a9c79fec94fe，制作脚本 SHA-256 641b7387345c6b1f1c26cfbb322459901340c818302c337aed788d86d0292ae6。只使用成功 manifest 对应的完整新 MP4；旧 produced 中断产物不用于通过。两 MP4 实算 SHA 与 manifest 相符：intro 7bad4256a5ef04bd737a54a3f81b1407217998e2c37d1e71e8633c0f0842162c（436318 字节）；workflow 8b879f20e88ad23e3e80916d7aa5a5ad67efb81ce50fb4bedd1bf09db712a627（49197093 字节）。source/asset 与本文 c33/36866 一致。

实际打开 intro 的 1/7/13/19 秒四页，分别为工作区、MODESWITCH、T09、POCKET9。标题、描述与完整长任务均在下方字幕区内，换行完整；上方 1600×1000 原页面、右侧控件和左下坐标轴保留，新增 240 像素字幕区未覆盖 UI。六个工作区标签完整分离，旋钮和 T09 主体完整清楚。POCKET9 页为低视角外壁，不能看清朝上的孔内，底座部分出下边；不能据该介绍页声称无遮挡孔口检查已满足。

workflow 时长 1308.44 秒。读取 manifest 与 frame_timing_verification：输入/输出均 32711 帧，全部相对 PTS 比较最大误差 0、时长误差 0，verification passed。这是制作工具记录的时序验证，本会话实际人工检查的是以下 13 个提取帧，没有逐帧观看全部视频。

|实际打开时间（秒）|代表内容与观察|
|---|---|
|1|白色加载页面，底部字幕完整；保留真实加载，不当转码丢失。|
|63|初始工作区就绪，PANEL/MODESWITCH/T09/MAG/POCKET9/T03 六标签完整，主体可辨。|
|331|初始暂停，右侧四步任务完整，旋钮箭头、PANEL 提示、T09 轮廓和 T03 检查环可辨。|
|423|中途暂停，旋转提示推进，原工作区和完整任务侧栏保留。|
|495|临时 T03 拉钉检查，拉钉头部和颈部清楚，检查环未盖住中心目标；侧栏显示挂起 1 组计划与恢复说明。|
|520|原四步计划已恢复，MODESWITCH 特写和旋转提示清楚，实体指示条仍向上；不把 ghost/提示当已确认旋转。|
|543|旋转提示到终点等待，实体指示条仍向上，未据图精确量角。|
|809|T09 ghost 到 POCKET9 顶部，实体仍在原支台；剩余 T09/T03/PANEL 三步，六标签可辨。|
|888|终点接收口低视角仍遮住孔内，ghost 向上伸出页面边缘。保留原视角/ghost 裁切限制，非新增字幕或转码裁切。|
|937|T03 拉钉头部、颈部与检查环完整，侧栏剩余 T03 检查和 PANEL 提示。|
|994|工作区显示计划完成、无待执行步骤；T09 已入 POCKET9、原位空出，六标签完整分离。引线局部遮挡仍保留 P3。|
|1231|无提示环的 T03 拉钉头颈完整清楚，刀柄下部出边属局部检查范围。|
|1305|末尾 PANEL 主体、四按钮及 TRAINING READY 文字可辨；显示区绿字对比偏低但仍可读，侧栏显示计划完成。字幕与原页面完整。|

这 17 张代表帧未见新增字幕出边、覆盖 UI、转码裁切或实质任务状态误导。POCKET9 孔内低视角不可见、终点 ghost 出顶边和局部引线遮挡仍为实际视觉限制；未证明 anchor 算法错位。未检查音轨，不将 CNC 视频代表帧视为 native Blender 通过，也不推广为其他 10 场通过。当前视频累计 blocks 15 + CNC 17 = 32 张唯一提取帧，逐帧哈希见 video_review_manifest.json；原生仍为 DIVE 46 张。

## connector 视频补审：新增 17 帧及 1 张来源对照原图

来源 videos/connector_attempt01/connector/produced/，session 03c4e01220234c6d8c82d775b7fb7b6b；制作脚本 641b7387345c6b1f1c26cfbb322459901340c818302c337aed788d86d0292ae6，source/asset 与本批一致。两视频实算 SHA 与制作 manifest 相符，逐项见 video_review_manifest.json。workflow 596.72 秒；工具记录输入/输出均 14918 帧，全部相对 PTS 和时长误差均 0、verification passed；不冒充本会话逐帧人工观看。

实际看 intro 1/7/13/19 秒：工作区、P、S、C 四页。字幕完整换行，原 1600×1000 UI 与坐标轴保留，下方 240 像素字幕未覆盖页面。P 与 C 主体完整；P 展示 ALIGN KEY 背壳，不是四针前端视图；C 展示正面，背面由 workflow 补充。S 下排两孔完整、上排两孔被壳顶遮挡，介绍文字写四孔可见不能当作此帧四孔全部可见的证据。

新增可见性限制：本次 3D 画布整体明显偏白、低对比，P/S/C 标签、实体颜色和 cyan ghost 都较淡；UI 黑字和字幕正常。另只读下载并实际打开同会话 intro_00/viser.png，原始截图同样偏白，因此没有证据将此归因于转码。标签、主体、步骤与检查部位仍能辨认，但本场不能描述为高对比展示。该 1 张来源截图单独列在 source_comparison_images，不计入 native 或视频提取帧数量。

|实际 workflow 时间（秒）|视觉观察|
|---|---|
|1|白色加载页，字幕完整。|
|42|初始工作区完整，P/S/C 三标签分离，但对比偏低。|
|165|P 插接和 C 背面两步原计划暂停，C 青环可辨。|
|229|P ghost 已沿路径移动，实体仍原位；提示较淡，工作区和侧栏完整。|
|274|临时 C 背面检查，黄色键和四个接触点完整，青环未盖住目标中心；侧栏显示原计划挂起及恢复说明。|
|305|原 P/C 两步计划恢复，ghost 在路径中；输入栏仍为临时指令，不误认当前执行目标。|
|354|ghost 到 S 接收区终点，P 实体仍原位，未确认插入。|
|391|S 接收视图下两孔可见，上两孔壳顶遮挡；ghost 覆盖接收区并出左/下边，不能作为无遮挡四孔证据。|
|426|原计划 C 背面检查，定位键与四接触点完整，剩余一步。|
|443|任务完成无待执行步骤；P 已在 S 前方接入位置、原位空出，三个工作区标签分离。|
|503|P 的 ALIGN KEY 背面标签完整，未展示针脚侧。|
|561|S 的 RECEIVER 后标签完整，不是孔口侧。|
|592|末尾无提示环的 C 后键、四接触点和 REAR KEY + CONTACTS 字牌完整；UI 顶部显示当前计划完成，字幕完整。|

本场 17 个实际视频帧未见新增页面/字幕裁切或步骤错指；保留原页面低对比、孔口自身遮挡与 ghost 裁切。当前累计 6 个 MP4、49 张视频代表帧、1 张来源对照原图；native 仍 46 张。其余 9 场等待各自完整新成片，不用失败/中断目录作通过。

## P2：connector 本次画布对比相对 RUN3 明显退化（只读对照）

按主线程要求重新实际打开 RUN3 的 01_start_paused/viser.png，与本次 intro_00/viser.png 比较。RUN3 桌腿、设备色彩与 P/S/C 标签均为正常深色；本次画布整体漂白、标签和 cyan 提示变淡。该变化已在本次原始 PNG 出现，且 workflow 暂停/终点/完成帧持续存在，不能用资产本来白色或仅介绍 idle 状态解释。定级 P2 为展示可见性退化；尚未证明由并发客户端引起，不擅自更改渲染参数或补做实验。

原图来源：
- RUN3：runs/simulation/cloud_continue90_20260921_6815e62/bridge_batches/connector/connector/01_start_paused/viser.png，SHA-256 54394706b1c4f944c4d0f855a6c39a16cf36f311bb30fb0b95da2f1c7405ead7；历史原图重复核看，不重复计入本批新图。
- RUN4：runs/simulation/cloud_finish90_20260921_e67b574/videos/connector_attempt01/connector/intro_00/viser.png，SHA-256 bad0e7fe3e3082ee6919be6f684f215d9e671cb3fe8dfb0a20bf97ecaafe9b0e；已计 1 张来源对照图。

独立读取 RUN3 bridge_connector_command/execution.json 的 source_before、assets_final.json，以及 RUN4 videos/connector_attempt01/provenance_before.json：source 均 c33e1ae4cdd7251c217e61caa31a2d58668984b0db6653d1fe4ac29929862e2a，asset 均 36866cf33627a522897a66a3e1247587608d72959dc792d029de0136a0b78af8。scene_fingerprint 同为 bddd94bff903c9dea3356fd9a7cafd4e7257bba4ecf45d3ba80113b98061d669，object_poses 一致。

view_state 的相机 position/look_at/up/fov/aspect/focus、brightness=1、enabled=true、workspace 与 selected=P 完全相同。不同项为 session、时间、revision/epoch/execution，playback_speed 0.1→1.0，以及 elapsed_s；snapshot 的 RUN3 paused 有两 cue，本次 intro idle 无 cue，其余共同显示字段相同。原图尺寸均 1600×1000、canvas 1276×1000。详细记录见 connector_display_comparison.json。

同相机无任务提示的桌腿 ROI [150,750,1000,990] 只读 RGB 拟合，本次≈0.238782×旧图+193.981893，中位绝对残差 0.275（8 位像素单位），描述为近似整体浅白混合；该数值不是致因实验或渲染根因证明。字幕排版完整与制作时序通过仍有效，但不抹去本次 P2。

## 漂白影响范围有限排查：另 6 张原始 PNG

主线程通知定位到 Viser HDRJPGEnvironment 淡入状态竞态；此处属于主线程代码调查结论，本会话不将通知冒充独立根因验证。按要求只读下载并实际打开以下 6 张已完成 PNG，最新阶段从 browser_capture.passed=true 的已存在 viser.png 按 mtime 选择，不读取未完成采样：

|来源|首/末阶段|实际颜色对比|
|---|---|---|
|bridge_batches/drone_bench_attempt02/drone_bench|01_start_paused、step_01_start|两图正常。首图 8 个标签黑字清楚、桌腿深色；最新 GUARD 箭头为饱和青色，指示条可辨。没有 connector 式漂白。|
|videos/control_panel_attempt01/control_panel|intro_00、object_C_inspection|两图正常。A/B/C 黑标签、C 深绿后壳与金色定位键/四接触点清楚。|
|videos/engine_bay_attempt02/engine_bay|intro_00、object_CONN_inspection|两图正常。六黑标签、深蓝机盖和 CONN 棕色后壳颜色正常，后键和四接触点清楚。|

这 6 张唯一原图单列 display_triage_manifest.json（2 张 native Viser、4 张视频来源 PNG），不混入已闭合 DIVE 的 46 张配对原图、不混入 49 张视频提取帧，也不将首末两图推广为所有中间阶段或整场通过。此前 connector 来源对照 1 张仍单列；历史 RUN3 对照复看不新增计数。以上三组未观察到漂白，不能因 connector 失败而假定全部受影响。

## Control 视频补审：实际 3 页介绍，新增 14 个代表帧

来源 videos/control_panel_attempt01/control_panel/produced/，session 0314d58af0ca4fc9aef3a29bc7e9461c，制作版本 641b738…，source c33/asset 36866。两 MP4 实算 SHA 与 manifest 一致。介绍实际为 18 秒 3 页，完整审阅 1/7/13 秒，不虚记第 4 页。三页是 workspace、B detail、C detail：字幕完整换行，顶部 1600×1000 UI 保留，介绍与流程所有所看帧颜色对比均正常，无 connector 式漂白。C 页前壳及主体可见、底座下部出边；背面由流程补充。

workflow 400.32 秒。制作记录输入/输出 10008 帧，相对 PTS/时长最大误差 0、verification passed；本会话人工范围为以下 11 个提取帧，非逐帧播放。

|时间（秒）|实际视觉观察|
|---|---|
|1|白色加载页，底部任务字幕完整。|
|25|A/B/C 全景标签黑字分离，主体入画，对比正常。|
|115|B 逆时针 30 度与 C 背面两步任务暂停，两个提示可见。|
|151|旋转进行后暂停，工作区、提示与任务侧栏完整。|
|184|临时 C 检查，黄键和四接点清楚，青环局部过外壳边缘但不盖中心；挂起原 B/C 计划与恢复说明可读。|
|216|B/C 原计划恢复，B 顶视指示条和旋转箭头完整，部分刻线被箭头遮盖，底部 B 字牌出原页面下边。|
|259|B 提示到终点等待，实体指示条仍朝上；不把提示到位当已确认旋转。|
|284|C 原任务检查，黄键与四接点清楚，侧栏只剩检查一步。|
|302|当前计划完成、无待执行步骤，A/B/C 标签完整，B 指示条朝向已改变。|
|356|无提示 B detail：旋钮完整，指示条相对 intro 朝向改变，底部 B 字牌部分裁切；未作精确 30 度量测。|
|397|末尾无提示 C 背面，黄键/四接点/后字牌完整，UI 显示计划完成。|

14 个代表帧字幕均完整、没有新增 UI 覆盖或转码裁切。原局部特写字牌出边、箭头遮住部分刻线仍保留。当前视频累计 8 MP4、63 帧（blocks15+CNC17+connector17+Control14），其中 connector 的 P2 漂白保持待修复重审；其余 8 场待各自完整产物。

## Engine attempt02 视频：新增 18 个代表帧

来源 videos/engine_bay_attempt02/engine_bay/produced/，session 6e74c9e94d2c4c1cab20e6e6b26a3060，制作版本 641b738…，source c33/asset 36866。两 MP4 实算 SHA 与 manifest 一致。只使用成功 attempt02 完整成片，attempt01 失败历史不改。intro 实际 24 秒 4 页，已看 1/7/13/19 秒；workflow 1346.92 秒，制作记录输入/输出 33673 帧，PTS/时长误差 0、verification passed，非人工逐帧检查。

四页介绍依次为工作区、CLAMP、PLUG、PLUGPORT。六个工作区标签分离，色彩正常；CLAMP 六角头与横向指示槽清楚，卡箍带/背景局部出边属局部特写。PLUG 全部主体入画。PLUGPORT 正视空孔口、内壁及底部圆面可辨，上下散热筋遮住外圈部分但孔口未被堵住。所有介绍页长任务字幕均完整，1600×1000 原页面保留，下方字幕未遮 UI。

|workflow 时间（秒）|实际视觉观察|
|---|---|
|1|白色加载页，完整字幕。|
|89|初始工作区，六标签可辨，对比正常。|
|350|初始暂停，CLAMP/PLUG/CONN 三步计划完整；提示可辨。|
|469|旋转中段暂停，工作区及三步计划保留。|
|540|临时 CONN 检查，后键/四接点/字牌完整，侧栏显示原三步计划挂起及恢复说明。|
|563|恢复三步计划，CLAMP 正视六角头及横槽完整，旋转箭头清楚；周围卡箍部分出边。|
|588|CLAMP 提示到终点，实体槽仍横向，不能记已确认旋转。|
|780|PLUG ghost 在原位与接收口之间，实体仍原支台；剩余 PLUG/CONN 两步。|
|898|ghost 到 PLUGPORT，实体仍原位，保持终点等待。|
|964|接收孔圆缘完整，ghost 覆盖孔内；不能据这帧作无遮挡孔内判断，介绍 19 秒另有空孔证据。|
|990|CONN 后检查，后键、四接点与字牌完整，剩余一步。|
|1042|计划完成，PLUG 已在 PLUGPORT、原支台空出，六标签文字分离；CONN 引线穿过前框区域有明显不可见段，按 P3 可见性限制保留，不断言 anchor 错位。|
|1115|CLAMP 无提示 detail，指示槽相对介绍由横向变为竖向，螺钉主体清楚；未精确量测 90 度。|
|1343|末尾无提示 CONN 后键/四接点/后字牌完整，UI 显示计划完成。|

全部 18 个实际帧对比正常，未见 connector 式漂白、字幕出边或新增页面裁切。保留终点 ghost 覆盖孔内、局部特写范围裁切及 CONN 引线部分遮挡，不以视频代替独立定向 native pairs。该阶段当时累计 10 个 MP4、81 个代表帧；后续 connector 重采复核、其余成片及 Engine 定向配对现均已审阅，见后文与最终结论。


## dig_site_attempt01 完整成片代表帧审查

已实际打开该 produced 目录两 MP4 的 18 张提取帧：intro 1/7/13/19 秒（实际 4 页、24 秒）；workflow 1/38/168/221/264/285/305/404/477/511/540/594/604/646 秒。session 0bd3ae1f251c4665a6d7edd8c7a05aa9；manifest source c33e1ae4…、asset 36866cf3…、production 641b7387…，完整值及视频/逐帧 SHA 见 video_review_manifest.json。workflow 649.04 秒，manifest 的输入/输出均 16226 帧、全部归一化 PTS 最大误差 0；这是程序时间证据，不等于人工逐帧观看。

所有已查看场景帧颜色正常，未见 connector 式整画布漂白。1600×1000 原页面与右侧 UI 完整保留，字幕位于页面下方附加区域，长任务中文两行完整、未覆盖页面。1 秒仍为初始白页；38 秒已有完整七标签工作区。

|代表帧|实际观察及限制|
|---|---|
|intro 1/7/13/19|工作区及 POT3、FLAG、BONE 介绍均完整显示。POT3 detail 是外壁，其三道内壁纹理由后续 inspection 覆盖；FLAG 红底 MARK 对比较低但可读。|
|workflow 168/221|原计划暂停，工作区七标签与全部主要对象可辨；不能据暂停截图声称动作正在执行。|
|264/285/305|临时 POT3 内壁检查及挂起原三步骤可见，随后恢复原计划；三道刻纹完整，青色检查环覆盖中部一段，页面记录仍暂停。|
|404/477|FLAG ghost 从中途移到 BONE 旁终点，实体仍在原托盘；终点提示不当实体已完成放置。STAY 青环仍见。|
|511|BONE 特写完整；此角度没有显示 FLAG 接地点，不作为接地证据。|
|540|当前计划完成；实体 FLAG 已在 BONE 旁，原托盘旗消失，七标签重新分离，位置关系可辨。|
|594|POT3 三条无提示内壁刻纹全部清楚，页面计划完成。|
|604|无提示 FLAG 完整杆、旗与杆底均入画，位于 BONE 旁；地面纹理/深度参照不足，不能单凭该帧定量证明精确接地或排除穿透。|
|646|末尾 TROWEL 手柄、接杆、三角刃完整，测绳在前方穿过但未遮住主要检查部件，页面计划完成。|

本场代表帧未发现需拒绝成片的新视觉缺陷。P3 引线局部遮挡和局部接触判断限制保留；FLAG 关闭提示侧视当时尚待审阅，现已完成并见 Dig 定向配对末节，不能以此视频替代。该阶段当时视频累计 12 个 MP4、99 张实际查看提取帧；其中 connector_attempt01 功能完成但视觉 P2 拒绝仍保留，未被本场正常结果覆盖。DIVE 原生 46 张、来源对照原图 1 张、排查原图 6 张分别计数，历史材料不重计。


## drone_bench_attempt02 完整原生 20 阶段

独立读取 bridge_batches/drone_bench_attempt02/report.json，session ce1533babfa144a89cf5ef5266db1cda，20 stages、passed=true、browser_errors=[]。已下载并实际打开每阶段 viser.png 与 frame_0000.png，共 40 张；此为 clientfix 安装前的 c33/asset36866 批次，不能冒充安装后回归。前期漂白排查中的 01_start_paused 与 step_01_start 两张 Viser 图本次重复打开，但按原始路径计唯一图时不重复累计。manifest 的 sha256 为实际 PNG 字节散列，不采用 report 中含义不同的 frame_sha256 字段冒充图片哈希。

|阶段（每行两端原图均已看）|实际视觉结论|
|---|---|
|01_start_paused|八个工作区标签完整、对象可辨；电池实体仍在支台，ghost 重合原位。桌腿下端出边，主要操作对象全在画面内。|
|02_middle_paused|BAT ghost 悬在 BAY 上方、实体在支台；四步计划与提示可辨。|
|03_temporary_inspection|M3 环形减震垫、孔缘、电机轮廓、青色环完整；中心 Viser 平亮、Blender 暗，不能据颜色推断孔的贯通性。|
|04_original_restored|恢复 BAT 工作区，ghost 在接收仓上方，两端目标位置相符。|
|05_endpoint_waiting|ghost 进入 BAY，实体尚未移动；仍暂停，不当确认后状态。|
|05_endpoint_receiver|BAY 上开口、四壁和底面轮廓完整；粒状 ghost 覆盖内部，不能称无遮挡底面检查。后方仪表青环顶部出边，选中对象 BAY 完整。|
|step_01_start|GUARD 顶面指示条向上，顺时针箭头完整入画。|
|step_01_middle|箭头端点前移，实体指示条仍向上，两端一致。|
|step_01_endpoint|箭头到终点、实体指示条仍向上；未确认阶段不当实体已旋转。|
|step_02_inspection|M3 指定减震环检查部位清楚完整，指引环未裁切；两端几何一致。|
|06_final_workspace|当前计划完成，BAT 已在 BAY，原支台空出；八标签完整，GUARD 指示条方向改变。全景引线局部穿过遮挡，未发现文字缺失或目标错认。|
|object_BAT_detail|BAT TRAINING 字牌全见，电池位于仓内，周围壁及 GUARD 可辨；仓壁遮挡电池侧面属于装入后视角。|
|object_BAY_detail|仓已被 BAT 占据，不能以此代替空仓底面检查；外壁轮廓完整。|
|object_GUARD_detail|旋钮顶面、指示条、圆周肋纹完整，底座下缘出边；与原顶视相比可见方向改变，但不同视角图片不做精确 30 度量测。|
|object_M1_detail|选中电机、轴头、肋纹、底座完整，连接臂通向外侧；背景仪表部分出边。|
|object_M2_detail|选中电机与底座完整，两端形状对应。|
|object_M3_detail|电机与减震环清楚，前连接臂遮挡底座一部分；减震环在侧面，详细正面见下一 inspection。|
|object_M3_inspection|无提示环时减震环整圈、孔缘完整无遮挡；Viser 中心平亮与 Blender 暗部材质/光照观感不同，未据此证明几何缺失或孔深。|
|object_M4_detail|电机轴头、肋纹、底座完整，连接臂一端出边；选中主体未裁切。|
|object_VOLTMETER_detail|VOLTMETER / TRAINING READY 全字与四按钮完整；显示的是训练状态文本，没有电压数值，不声明读数正确。|

本场全部 20 张 Viser 页面颜色正常，没有 connector_attempt01 那种整画布漂白；Blender 灰底和柔光属于渲染差异。操作对象和配对几何目视对应，保留 ghost 内部遮挡、局部底座裁切、P3 引线遮挡及孔内可判定深度的限制。捕获协议通过与这些视觉边界分别记录，不宣称无任何视觉限制。本批 native 清单累计 86 张唯一原图；video 仍为 12 MP4/99 帧。6 条排查记录中的 2 张与 native 重合；加 4 张额外 UI 排查图及 1 张来源图后，当前原图总计按 91 张唯一源文件计，而不能将 86+6+1 写成 93。


## clientfix 后 connector_attempt02 四张 intro 来源原图

已实际打开完成的 intro_00/01/02/03/viser.png，分别是工作区与 P/S/C 特写。四张均颜色和对比正常：深色桌腿、蓝色 P、绿色 C、黑色 P/S/C 标签可见，旧 attempt01 的整体漂白在这四张中已消失。P 对齐键与字牌清楚；S 上两个孔仍被顶壳部分遮挡、下两孔完整；C 当前为外壳正面，背面检查须待 workflow。

这四张记录独立列于 clientfix_visual_manifest.json，不计入 native 配对或 MP4 提取帧。已读取实际 served_client.json：实际收到的 HTML 与 installed_build SHA 均 db213945693b3efd036c6d2c6c27eca2147ea7648a95938d3a8fcd218a15be2f；provenance source 仍 c33e1ae4…，capture_script 为 76e53bfe4d64649b393c8bd5cace95fe0bf70fdbf6081bde96bc7f524a7cfa0e。四阶段 canvas_before/after passed 均为 true；intro_00 实际 canvas opacity 1、各祖先 opacity 1，是只读 DOM 辅助证据。未操作 DOM 或浏览器；未将新 intro 正常提前升级为完整 workflow/成片通过。旧 connector_attempt01 P2 拒绝保留，新成片完成后再独立审查。

增加上述四张后，当前唯一原图为 95 张（native 86 + 额外排查 4 + 旧来源对照 1 + 新 clientfix intro 4）；MP4 仍 12 个、实际提取帧仍 99 张。

## 新客户端 connector attempt02 成片：旧 P2 已在代表帧范围解决

来源 videos/connector_attempt02/connector/produced，session 404acb58573a47d5adde618f148c8e86。制作脚本 641b7387345c6b1f1c26cfbb322459901340c818302c337aed788d86d0292ae6；采集脚本 76e53bfe4d64649b393c8bd5cace95fe0bf70fdbf6081bde96bc7f524a7cfa0e。此前独立读取的 served_client.json 对应实际客户端 build db213945693b3efd036c6d2c6c27eca2147ea7648a95938d3a8fcd218a15be2f，应用/资产仍为本报告 c33/36866 身份。

实际打开 intro 1/7/13/19 秒四页，workflow 1/30/154/213/250/284/332/368/397/420/468/525/556 秒十三帧。intro 24 秒；workflow 559.96 秒，manifest 输入输出 13999 帧、全 PTS 检查 passed。该自动时序证据不代替人工视觉。

全景 P/S/C 黑色标签、蓝灰实体、透明提示均有正常对比；原 1600×1000 页面及其下方字幕完整。250 秒临时 C 背面四端子/定位键和圆环完整，284 秒恢复 P，332 秒 ghost 到位而实体仍在原位，397 秒 C 背面检查，420 秒任务完成、P 已插入 S、旧位置空出。末尾 556 秒无提示 C 背面完整。17 帧没有旧 attempt01 的全场漂白，允许接受新 attempt02 的本次视觉范围；旧 attempt01 继续 rejected，证据不覆盖。

限制保留：S 上两孔被顶壳部分遮挡，下两孔可见；368 秒接收口 ghost 覆盖孔口并在左下出框；468/525 秒是 P/S 背面标签视角，不能声称展示正面四针/四孔。未做全片逐帧人工审阅。

## Infusion 成片：4 页介绍 + 17 个 workflow 代表帧

来源 videos/infusion_ward_attempt01/infusion_ward/produced，session 6b5b8ef7dc924049808bb4106c0e67a5；source/asset 同本报告，制作脚本同 641b7387。实际打开 intro 1/7/13/19 秒；workflow 1/33/133/178/213/241/286/315/340/360/405/447/462/513/528/542/556 秒。intro 24 秒、workflow 559.24 秒；仅记录实际查看的 21 帧，不声称全部对象细节已人工覆盖。

介绍四页呈现六标签工作区、泵盒、SLOT2 开口和 BAG1；开口完整、两底部导条可见。四页字幕及 workflow 三行任务字幕全部位于页面下方，文字无裁切。1 秒白色初始页后 33 秒场景正常，未见漂白。133 秒原四步骤暂停，178 秒 ghost 在途，213 秒临时 BAG2 背面 TRAINING B 可读，241 秒恢复原任务，286 秒 ghost 在 SLOT2 而实体仍在桌面。315 秒接收口四边和导条完整，ghost 覆盖内表面，外围设备出框，不据此确认内部接触深度。

340 秒 BAG1 的 TRAINING A/SIMULATION ONLY 可读，检查环经过部分字母但未遮断语义；360/405/447 秒蓝色旋塞实体待确认，顺时针提示箭头在变。462 秒页面计划完成、泵盒入槽、旧桌面空出、旋塞方向已变，六标签齐全。513 秒无提示旋塞本体完整，528/542 秒两袋背面字牌完整，556 秒 MONITOR 的 TRAINING READY 及四按钮完整。背景立柱、地板边缘及部分安装盒外框出画面属于局部视角范围，主要目标未见被裁断。没有出现旧 connector 的 P2 漂白；保留 ghost/检查环局部遮挡和 P3 引线可见性限制。此视频通过与仍在运行的原生 Infusion 验收不混同。

## 最终显示响应：单列 7 张原 PNG

独立清单 response_visual_manifest.json，均实际 view_image 打开、逐图本地与服务器文件字节 SHA 一致。这 7 张不增加 native 86 或视频代表帧 137 的计数；其他源 PNG 95 张另计。只读取已完成产物，没有操作参数或重跑实验。

Optical session 95ab06628f5446c982f46b402c1dea84：实际查看 viewer_response_final/optical_bench/{workspace,brightness_zero,brightness_one,defocused}.png。workspace 原完整 UI 显示五标签、台面主要光学组件和暂停状态，近处桌腿底部出框；标签没有丢失。后三张为已保存的 1276×1000 canvas 图，并非完整 UI。brightness_zero 中青色 ghost 和镜面提示消失，brightness_one 中恢复，实体和文字保持可辨；未见全场漂白。defocused 相对 brightness_one 的提示变化很细微，原图肉眼不足以称为明显的整体失焦，未见设备或标签消失。

已读最终 report 与 comparison：亮度全 canvas changed_pixels=2585，focus=312，report status=passed、browser_errors=[]；focus_m 记录由 2.2290446576421674 改为 2.579。这是页面响应和整画布差分证据，不能据此证明真实光学焦深、光学校准、物理亮度或变化的空间局域性；也不把 312 像素变化描述成显著视觉改善。

Control session 35c8f18eb844498ca40113ff399637e3：实际查看 response_final/{count_high,count_low,sigma_wide}.png，均为保存的 canvas 图。三图同一 C 背面定位键、四端子及 REAR KEY + CONTACTS 文字完整；count_high 青环较平滑连续，count_low 出现可见节段和粗细起伏，sigma_wide 成为宽而半透明的带状环，覆盖更多壳体边沿与牌框，中心键和四端子仍可辨。没有旧 connector 的全场漂白。

最终 report passed=true、browser_errors=[]，N high→low 全 canvas changed_pixels=76050，low→sigma_wide=351288；指标已明确 Whole-canvas，不能当作局域支撑面积或空间局部性证明。实际变化支持显示参数影响提示外观，不能外推到真实设备/光学标定。

## DIVE 视频成片：新增 24 张实际代表帧

来源 videos/dive_fillstation_attempt01/dive_fillstation/produced，session 046dbc5bbebf445ea479ba7953125201，source c33、asset 36866，production 641b7387。介绍 24 秒四页，实际打开 1/7/13/19 秒；workflow 537.24 秒，实际打开 1/25/126/159/190/207/227/245/282/318/333/354/384/413/427/474/490/510/520/531 秒二十帧。manifest 的全帧时间比较 passed、最大相对 PTS 误差 0，是自动时序证据；本节仅人工代表帧范围。

四介绍页分别为七标签工作区、BOTTLE3、QRC、VALVE。BOTTLE3 主要瓶体完整，右支架没有盖住主体；VALVE 空口完整、内壁可见；QRC 的 DRY 前牌和外壳完整。介绍 BOTTLE3 的 TRAINING BOTTLE3 说明指其背面，介绍页实拍为前面普通 BOTTLE3，背面由 workflow 补足。原 1600×1000 页面与下方字幕完整，长文字三行仍在字幕区；已审帧全场对比正常，没有漂白。

1 秒原加载白页，25 秒已有正常场景。126/159 秒四步骤暂停可读；190 秒临时 BOTTLE2 的 TRAINING 字牌/环完整、原计划挂起，207/227 秒恢复 BOTTLE3。245/282/318 秒 QRC 的 ghost 由原位、在途至 VALVE，而实体确认前仍在台上。333 秒接收口局部被 ghost 覆盖，ghost 左侧出框；这是既有局部可见性限制，不当作完整孔深/内部接触检查。

354/384/413 秒 STEM 实体仍竖直、逆时针提示箭头方向变化，部分环段被实体遮挡；427 秒计划完成、QRC 接到 VALVE、旧台面空出、STEM 水平，七标签完整。474/490/510 秒三个瓶背面 TRAINING BOTTLE3/1/2 无提示牌完整，瓶体上下出框但文字未裁；520 秒水平 STEM 及转轴完整；531 秒末段三表盘外圈/刻线/指针完整，没有数字数值，不能称读到了具体压力。已有全景 BOTTLE3 支架遮挡、引线 P3 间隔保留。不混同已完成 native 23 阶段证据，也不声称全片逐帧人工通过。

## Optical 成片：新增 23 张实际代表帧

来源 videos/optical_bench_attempt01/optical_bench/produced，session 6238ae8297ea44a79f6436dde48c1b63，source c33、asset 36866、producer 641b7387；独立读取 produce_video_optical_bench_01_command/execution.json returncode=0。intro 四页 24 秒，实看 1/7/13/19 秒；workflow 727.36 秒，实看 1/40/198/254/291/324/369/400/438/490/539/562/585/615/642/667/693/704/724 秒，未人工逐帧观看全片。

介绍页五标签 TARGET/M/L2/POST2/L1 可读，L1 镜面与环形框完整，POST2 空孔、筒身和锁紧侧钮完整；M 初始镜面、左右支架、刻度盘和指针可见，底座下沿局部出框。M 页背面编号描述由后续检查补充，当前页是正面。全片所审页面及其下方两行字幕完整，无整体漂白。

198 秒四步骤暂停，254 秒 L1 ghost 在途而实体仍旧位；291 秒临时 M 背面 HR-45° 1064 字牌和左右调节端头清楚，324 秒恢复 L1，369 秒 ghost 到 POST2。400 秒套筒、孔口和侧钮完整，但 ghost 主镜面在画面顶端被裁，接触内深度不可由此确认。438/490/539 秒为 M 俯视旋转提示，镜面/支架主体完整，部分提示环被实体遮挡；确认前主体方向未变，不能把箭头终点当作实体完成。

562 秒 M 背面字牌/检查环完整；585 秒计划完成，L1 已装 POST2、旧底座空出、M 朝向有变化，五标签齐全。615 秒 L1 环形镜框完整、下方套筒底端出框；642 秒 POST2 筒身和侧钮完整，上方 L1 镜框出画属于接收器局部视角；667 秒 L2 镜框完整而底座下沿出框。693 秒 M 镜框及刻度指针完整，指针与 intro 19 秒位置不同，可见方向改变，但不同局部视角不用于测量精确 15 度。704 秒无提示 M 背面字牌完整，724 秒 TARGET 全边框、同心圆和十字线完整。背景对象被选中主体挡住/出框不记为主体缺失，保留 P3 引线及局部提示遮挡限制。


Optical M 表面补充（仅复用已审帧）：intro 19 秒的实际圆形镜面可辨，表面为银白/浅灰高光，右侧有较深灰黑渐变及柔和反射纹理；外围蓝灰金属环与镜面之间有清楚边界，左右方形支架也能区分。workflow 693 秒镜面仍完整可辨，呈更均匀银白浅灰、带淡灰模糊反射纹理；蓝灰金属环并未消失或与白背景混成一体。该帧镜面较亮是表面自身呈现，周围金属、桌面、UI 仍有正常对比，未见旧 connector 那样整幅画布透明漂白。此结论来自实际表面原视频帧，而非只凭指针/背面字牌；不能用不同观察角的亮暗或指针位置量化精确 15 度，也不验证真实物理反射正确性。

## Drone 成片：新增 27 张实际代表帧

来源 videos/drone_bench_attempt01/drone_bench/produced，session 11daa80061d245a48d9ed66db1100e5a，source c33、asset 36866、producer 641b7387；独立读取 produce_video_drone_bench_01_command/execution.json returncode=0。intro 四页 24 秒，实看 1/7/13/19 秒；workflow 907 秒，实看 1/38/204/266/306/339/386/425/477/535/591/617/639/675/725/773/808/833/857/861/865/885/904 秒。22675 帧时序校验来自 producer，人工仅查看上述代表帧。

介绍工作区八标签完整；BAT 壳体及 TRAINING 正牌完整，BAY 空仓四壁和底面可见，GUARD 锁扣顶面和索引条完整、底部外壳下沿出框。四页及 workflow 所审原 1600×1000 页面和下方字幕完整，长字幕三行仍在边界内，没有整体漂白。

1 秒为原录像加载白页，38 秒已有正常场景；204 秒四步计划暂停。266 秒 ghost 在 BAY 上方、实体 BAT 仍在旧位。306 秒临时检查 M3 的金黄色环状减震垫及灰色孔心完整、外提示环完整，原四步计划挂起；339 秒恢复原四步；386 秒 ghost 到仓内。425 秒 BAY 四壁、口沿完整，但 ghost 覆盖部分底面，后景 VOLTMETER 提示环顶部裁切，不能据此验证导轨底部接触。

477/535/591 秒为 GUARD 顺时针提示的开始/中间/终点：箭头方位变化，实体索引条仍竖直直到确认。617 秒 M3 检查环与减震垫完整。639 秒 UI 当前计划已完成、BAT 已在 BAY、旧位空出、八标签齐全。675/725 秒 BAT TRAINING 字牌和包围仓壁完整，仓底被实体电池挡住；773 秒无提示 GUARD 索引条方向已改变，底部外壳下沿出框，不用不同角度量化精确 30 度。

808/833/885 秒 M1/M2/M4 电机主体完整，连接臂部分出框；857 秒 M3 减震垫可见，连接臂遮住部分电机底座；861 秒 M3 无提示正面检查中减震垫、灰色孔心、外壳完整。865 秒实际已切到 M4 的放大过渡画面、底缘裁切，按过渡帧记录，不误称 M3 检查完成帧。904 秒末尾 VOLTMETER TRAINING READY 字牌、边框和四按钮完整，没有具体电压数字。保留既有 P3 引线与局部遮挡限制；此成片与 native 20 阶段分别计证。

## Server Rack 成片：新增 20 张实际代表帧

来源 videos/server_rack_attempt01/server_rack/produced，session 6a1b96c548494c0c8d96199346652a79，source c33、asset 36866、producer 641b7387；独立读取 produce_video_server_rack_01_command/execution.json returncode=0。intro 四页 24 秒，实看 1/7/13/19 秒；workflow 1049.36 秒，实看 1/69/330/421/493/562/651/724/760/812/880/917/981/1014/1027/1046 秒。不是全片逐帧人工审查。

四介绍页展示五标签工作区、SPARE、SLOT4、NODE3。两个节点外壳、前牌和双把手完整；SLOT4 左导轨及后挡可见，右导轨局部被机架立柱挡住。NODE3 页背口描述对应后续检查，当前介绍图为节点正面。所审整页及下方两行字幕完整，画布对比正常、没有整体漂白。机架和小车底脚在部分全景下沿出框，操作对象完整。

1 秒是原加载白页；69 秒工作区正常；330 秒三步计划暂停，SPARE ghost 在旧位上方，421/562 秒在向槽位移动的中途位置，651 秒已到 SLOT4，而实体仍在左检修车。白背景上的稀疏淡青 ghost 对比偏弱，机架暗背景处更易辨认，记为局部 P3 可见性限制，不与旧 connector 的整幅漂白混同。493 秒临时 NODE3 背面 PORTS 牌、三根接头及一个圆口完整，提示环部分盖住中部接口；原三步计划挂起，562 秒恢复。

724 秒接收器视角的左右导轨/后挡仍可辨，右轨前端被立柱挡住，ghost 又盖住部分空间，无法从单帧核实完整侧面接触。760 秒 NODE3 背口检查，812 秒计划完成、SPARE 装入 SLOT4、左小车空出、五标签齐全。880/917 秒 SPARE 前面板、字牌、双把手完整，节点右后部及导轨被立柱部分遮挡。981 秒 NODE3 正面完整，1014 秒无提示背面 PORTS 牌及四接口位置完整；1027 秒 ALARM 三色段完整，1046 秒末尾 FAN 的圆面、索引条和散热外缘完整。本片不扩充历史 Server native 双通道证据。

## Infusion 原生完整 19 阶段：新增 38 张原图

来源 bridge_batches/infusion_ward/infusion_ward，session 08431a11918d4472bcdbeb17f703b1e3，report passed=true。实际查看 report 全部 19 阶段的 Viser/Blender 配对原图，逐图下载 SHA 与远端当前字节 SHA 一致；运行通过和以下视觉限制分别记录。

全景六标签 BAG2/BAG1/MONITOR/SLOT2/PUMPCASSETTE/STOPCOCK 齐全且可辨，主要操作对象完整；未见 Viser 整体漂白。开始、中途、恢复、终点等待的 ghost 分别在泵原位附近、移向接收槽及槽中，实体待确认时仍在台上。临时 BAG2 背面 TRAINING B/SIMULATION ONLY 和随后 BAG1 背面检查字牌完整，提示环穿过部分文字，字仍可辨。两袋无提示检查图的袋体、顶环及底部双接口全部入画。

05_endpoint_receiver 的 SLOT2 四壁、底部及双导轨可见，ghost 覆盖部分后壁和底面；主机外壳被边缘裁切，不能据此核实完整接触或落座。step_02 三阶段旋转箭头变化，确认前实体 T 形阀门仍保持原向；圆提示局部被立柱挡住。06_final_workspace 显示计划完成、泵装入槽、原台位空出，阀门分支转向右、主条竖直；六标签完整，PUMPCASSETTE 引线一段被显示器遮挡，保留 P3。

PUMPCASSETTE 细节中 TRAINING 前牌、圆角壳体完整，周围接收器外壳部分裁切；上下存在暗缝，不能仅凭这些图判定装配错误。SLOT2 细节外缘完整、内部导轨已被泵遮住；STOPCOCK 蓝色 T 形柄、轴及连接点完整，背景杆出框。BAG1/BAG2 正面牌和背面训练标识均完整。MONITOR 面板、TRAINING READY 和四按钮完整，下方支架出框，未显示数值生理读数。

Blender 与 Viser 的形状、位置、提示部位对应；Blender 呈灰背景、较浅且柔化的表面，白袋和顶环对背景对比较弱，青色提示较亮、扩散较多。该通道外观差异如实保留，不将其认定为已修复的浏览器 HDR 淡入竞态复发，也不据此声称光度一致。

## Engine 定向配对：4 张关闭提示原图

changed_pairs/engine_bay/report.json passed=true，session c97d8fe967584697b0a6a56b94dc1ad0。实际查看 empty_PLUGPORT_guidance_off 与 CLAMP_completed_guidance_off 各 Viser/Blender 两张原图，SHA 与远端一致。定向配对单独保存 pair_review_manifest.json，不混入 124 张完整原生流程或视频代表帧。

空 PLUGPORT 的圆口及内壁完整，中央孔口未被上下鳍片挡住，外侧圆底座被鳍片局部遮挡。Viser 孔底呈浅色圆面，Blender 孔底呈深色圆面；两端可辨内壁，但不据亮度断言通孔、物理深度或光度一致。CLAMP 完成态的六角调节头与近竖直深色槽/索引条完整，两端方向一致，未被提示遮住；周围箍带局部出框。单一完成视角不独立量化旋转 90 度或证明刻槽深度。

## 审阅副本有限清晰度抽查：独立 8 张帧

在 review_copy_visual_manifest.json 单列两份大媒体原件/副本，各选两个相同时间点，共实际打开 8 张提取帧。媒体 SHA 与对应 proof.json 一致，PNG 位于独立 review_copy_inputs/，不混入 video_review_inputs/ 或原生图计数。

CNC 的 raw_video/page@fd679b4363116b315b9edb7e864c0eb9.webm 对 review_video_55e5e360471e_a01/review.mp4，495 秒临时检查和 1231 秒无提示完成后检查：两端 T03 拉钉轮廓、青环及任务栏文字可辨，整页边界相同，无新增裁切。原件本来没有制片字幕，未要求副本增加。Engine attempt02 的 produced/workflow_realtime.mp4 对 review_video_490ba4cb7ed1_a01/review.mp4，540 秒 CONN 背面和 1115 秒 CLAMP 完成细节：四接点/后键、字牌、调节头及细索引可辨，右侧任务栏与下方两行说明字幕完整。

抽查帧未见妨碍审阅的额外模糊或裁切，不能据此称所有压缩帧无损，也不替代完整 PTS/时长核验。未抽查其他审阅副本。

## Shelf 成片：新增 20 张代表帧，保留 c33 来源

videos/shelf_picking_attempt01/shelf_picking/produced，session c2bf1e7aee224802ad9173d453a1b288，source c33、asset 36866、producer 641b7387；读取制作 execution returncode=0。intro 四页 24 秒，实看 1/7/13/19 秒；workflow 873.36 秒，实看 1/38/240/329/382/438/517/571/617/644/685/734/765/810/847/870 秒。两原始 MP4 SHA 与 production manifest 一致。

全景五标签 RED/BASKET/GREEN/CONV/BLUE 完整，主要设备及支腿入画，地板边缘部分裁切；画布对比正常，无整幅漂白。四介绍页展示工作区、完整红包裹、篮体和 BLUE 周转箱；介绍 BASKET/BLUE 的低视角看不到完整内底，BLUE 正面介绍不展示后侧面单，后续检查有覆盖。原 1600×1000 页面与下方两行字幕完整。

1 秒加载白页，38 秒工作区正常；240 秒四步计划暂停，329/438 秒 ghost 在层板前方中途位置，382 秒临时 BLUE 检查显示 BLUE/SHIPMENT 027 面单及框，原四步任务挂起；438 秒恢复。517 秒 ghost 到篮内、实体仍在架上，571 秒接收器视角前壁遮住 ghost 大部分和底部接触面，只能见篮后部淡青提示，不能证明落座深度。644 秒计划完成、RED 已进篮、架上原位空出，五标签齐全。全景白背景上的淡青 ghost 对比偏弱，作为 P3 范围限制保留。

685 秒 RED 细节被篮前壁挡住大半，只见上部和胶带，篮左/下边出框；810 秒 BASKET 细节能见 RED 顶面，仍不能看清篮底接触。734 秒 BLUE 前方箱体完整，765 秒无提示 BLUE 背面面单和外框完整。847 秒 CONV 的 TRAINING READY 面板及四按钮完整，870 秒末尾 GREEN 包裹和胶带完整，输送台边缘出框。这组已看帧没有显示背向错误；不因此否定另一次 Shelf 定向配对实际发生的相机同步失败。该视频保留 c33 身份；新 d8 修复版本的有限回归见后文，不由旧视频代替。

## Dig FLAG 定向配对：2 张关闭提示原图

changed_pairs/dig_site/FLAG_contact_side_guidance_off，session e26a6806299f4f3c8b1784cceff976bd，report passed=true、revision=0/epoch=0。Viser 和 Blender 原图实际查看，SHA 与远端字节一致，单独 pairs 清单累计 6 张。

MARK 字牌及整根旗杆完整，杆尖落在灰色支撑板边缘与浅色外沿的交界处，未见明显悬空光隙。杆尖与板边重合，不能从这单一角度精确量化接触/穿入深度或证明物理支撑稳定性；两通道颜色/阴影不同而轮廓相符。该图 UI 为等待任务、revision=0，是初始位置支持面的视图，不是确认后 BONE 旁的任务终点；不能替代后者接触证明。本阶段当时等待 Shelf 新来源回归；该回归现已完成并在后文单列 d8 结果，报告已定稿。

## 新源码相机回归：21 张独立 UI 原图

camera_atomic_live，resume03，session 2ab33eddf57f42b1870d003c31261d2e；独立读取 camera_atomic_live_command/execution.json 的 returncode=0、source before/after 均 d8d73e7d849b949bfee3827d6f60dfb86351cc50b49f98027b92db1664392806。result.json viewer 单文件 before/after SHA 为 98006df1f6b922b58136d814e8ee97d30d94c8505adeede0cd2850c66ed8f331，与项目摘要区分。资产维持 36866 来源。

实际查看 paused_endpoint.png 和 round_01 至 round_10 的 BLUE_inspection.png、BASKET_detail.png，全 21 张，下载 SHA 均与远端字节一致，camera_review_manifest.json 单列。十轮 BLUE 都正向显示完整 BLUE/SHIPMENT 027 字牌、外框、背面结构条与提示环；十轮 BASKET 都实际对准篮体，后内壁淡青 ghost 可辨，没有背向、空场景或目标错置。paused_endpoint 的 BLUE 主体和面单完整，但环的顶部/底部超出画面；切换后的十张 BLUE 环完整。篮前壁持续遮住底部 ghost/接触面，背景 RED 部分贴近或越过上边缘，篮体本身完整。

result 的 20 次 positive_in_range/focus_matches_contract 全为 true，辅助支持相机方向/焦点回归；这 21 张图仅证明本会话十轮真实 UI 切换的有限视觉覆盖，不视为新源码全部原生流程或全部视频重跑通过。

## 旧 Shelf 失败尝试的有限历史补看：4 张

changed_pairs/shelf_picking 的 BASKET_empty_guidance_off、BLUE_inspection_guidance_off 各 Viser/Blender 两图已实际查看并核对 SHA，源 c33，单列 historical_failed_attempt_partial_pair，pairs 清单当前 10 图中 6 图来自完整 Engine/Dig 配对、4 图来自此失败尝试前两个阶段。旧两阶段空篮体、四壁上缘和 BLUE 背面面单均完整；低视角篮前壁遮底，Blender 比 Viser 更浅。不能用这四张正常图否定第三阶段相机同步失败，也不计为新 d8 源码通过。新 Shelf attempt02 因 out 相对路径在启动检查阶段拒绝，主线程确认 rc1、无新图；不计入图数。正确绝对路径 attempt03 的最终结果见下节。

## Shelf attempt03 最终配对：新 d8 源码 8 张原图

changed_pairs/shelf_picking_attempt03/report.json passed=true、browser_errors=[]，session 57e94d5ad75043fc8c26d0d890cca895。独立读取 pairs_shelf_picking_attempt03_command/execution.json，returncode=0、source before/after 均 d8d73e7d849b949bfee3827d6f60dfb86351cc50b49f98027b92db1664392806；资产仍为 36866cf33627a522897a66a3e1247587608d72959dc792d029de0136a0b78af8。四阶段各两张原图已实际打开，下载 SHA 与远端字节 SHA 一致。

BASKET_empty_guidance_off 的空篮外壳、上沿和内壁完整，低视角前壁遮住底板。BLUE_inspection_guidance_off 的 BLUE/SHIPMENT 027 面单、边框和周围结构条完整可读，无提示遮挡。BASKET_endpoint_waiting_confirmation 正向对准篮体，淡青 ghost 位于篮内后部，实体 RED 仍在架上；篮前壁遮住 ghost 的下部和接触面。BASKET_confirmed_guidance_off 显示 RED 实体顶面/胶带在篮内，架上原位空出，UI 当前计划已完成且 BASKET 已接收 RED；此时没有提示遮挡，但包裹底面和篮底接触仍不可见。Viser/Blender 的对象、轮廓、状态一致，Blender 更浅、更柔；新八图未见旧背向视角或整体漂白。

新成功 8 图与旧失败尝试 4 图分别保留，不用新结果抹去旧相机同步故障，也不由这四阶段推断新源码全部场景 native 重跑通过。

## 封闭范围和来源

本报告依实际查看清单定稿，当前授权视觉审查已完成，无待审新文件。12 场视频与此前完整原生/Engine/Dig 配对保留项目 source c33e1ae4cdd7251c217e61caa31a2d58668984b0db6653d1fe4ac29929862e2a 身份；相机 21 图和 Shelf attempt03 8 图为项目 source d8d73e7d849b949bfee3827d6f60dfb86351cc50b49f98027b92db1664392806。两个来源不合并宣称为同一源码的全流程验收。旧 connector P2 拒绝、旧 Shelf 失败和启动错误证据保留。本文前段各追加记录中的当时累计/待办描述属于历史进度，以本节及开头最终清单为准。

保留的视觉限制包括部分引线被遮挡/局部间隔、淡青 ghost 对比偏弱、特写中的外围裁切和孔口/接触面遮挡、Viser/Blender 光度差异；没有用改相机、改渲染器或重建资产掩盖。几何接触、精确旋转角及物理光学校准不由这些图像作超范围结论。本会话将此报告和清单同步后冻结，不再修改，供主线程以 SHA 封闭 acceptance。
