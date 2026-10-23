# 固定资产来源与许可

当前场景按版本保存：原版为 `scenes/legacy/<id>/`，成熟素材重构版为 `scenes/reconstructed/<id>/`。下文早期条目中的 `scenes/<id>/` 是当时的目录名称；对应原版文件现在位于 `legacy`。各批重构新增的第三方许可适用于 `reconstructed` 中相应派生件。目录迁移不改变任何素材的许可。

本包的九组 GLB 和 OBJ 几何（现位于 `assets/meshes/common/`）、Gaussian 预览采样池由本次交付的生成脚本创建，使用原创基础几何组合。可在该项目中使用、修改和重新发布；固定资产按 CC0 1.0 提供。

这些是通用旋钮、模块、插接件和积木造型，不对应真实商业器件或品牌 CAD。GLB 包含顶点颜色，OBJ 提供简便的几何导入。几何单位是米，坐标为右手系、Z 轴向上。

Gaussian NPZ 是可重复的几何采样池，用于测试数量变化与接口。光学拟合与标定由全息后端提供。外部论文代码和模型权重均未打入本包，使用时遵循对应项目许可。

2026-09-17 v2 扩展（2026-09-18 套件化迁移）:五组扩展场景的交互对象位于 `scenes/server_rack/meshes/`、`scenes/drone_bench/meshes/`、`scenes/shelf_picking/meshes/`、`scenes/optical_bench/meshes/`、`scenes/dig_site/meshes/`,程序化环境件位于各套件的 `scenes/<id>/meshes/env/` 子目录,均为本项目原创生成,按 CC0 1.0 提供;PolyHaven 下载素材与其转换件（共享池 `assets/meshes/env/`）的来源与许可见 `assets/downloads/SOURCES.md`。

v3 发动机舱复刻轮（2026-09-17）：`assets/raw/engine_round/` 的 29 个 PolyHaven 模型与 2 个 HDRI 均为 CC0，来源/许可/校验见 `assets/raw/engine_round/SOURCES.md` 与同目录 `polyhaven_download_log.json`（155 条 md5 校验；两条 HDRI 的 md5 值为事后按本地文件补记并经 PolyHaven 线上 API 复核，见日志内 md5_note）。`scenes/engine_bay/meshes/` 六个交互对象与 `scenes/engine_bay/meshes/env/engine_*` 三个环境件为本项目程序化原创，同 v1 条款（CC0）。

2026-09-18 v4 新三场景套件:`scenes/cnc_toolchange/`、`scenes/dive_fillstation/`、`scenes/infusion_ward/` 三套件的全部交互对象与环境件（`scenes/cnc_toolchange/meshes/`、`scenes/dive_fillstation/meshes/`、`scenes/infusion_ward/meshes/` 及各自 `env/` 子目录）由各自的 kit builder（`scripts/scenes/build_<scene>.py`，Blender 3.1.2 程序化建模）原创生成，无外部素材引入，同 v1 条款按 CC0 1.0 提供。

2026-10-22 两场景素材重构：本段取代上文对 `shelf_picking` 和 `server_rack` 当前派生资产“全部原创、统一 CC0”的描述。货架场景复用 Poly Haven 的货架、纸箱、塑料筐、工具车及 PBR 材质，均为 CC0；来源见 `assets/downloads/SOURCES.md` 与 `assets/raw/engine_round/SOURCES.md`。服务器场景的 SPARE、NODE3 和机柜中的固定服务器使用 **Lenovo Rack SR-250 by impresistem, CC BY 4.0, via Objaverse/Ai2; adapted for HoloCue**。其纹理与几何的派生资产必须保留作者署名、原始来源、许可链接及改动说明，不适用上文 CC0 总括。机柜结构使用 Innerscene CC0 布局模型；工具车及地面材质使用已有 Poly Haven CC0 素材。完整逐项来源、原始文件和尺寸适配说明见 `assets/downloads/server_reconstruction/LICENSE.md`。所有商业品牌标记均来自原始模型，不表示品牌方认可。
2026-10-22 第二批素材重构：本段取代上文对 `optical_bench` 与 `dig_site` 当前派生资产“全部原创、统一 CC0”的描述。光学镜架、柱座与调节件来自 Brandon J. Winters 和 David Shepler 的开放光机 CAD（HardwareX，DOI: https://doi.org/10.1016/j.ohx.2017.12.001；https://osf.io/9kt52/），按设计文件表的 CC BY-SA 4.0 保留署名与改动说明；OSF 节点当前 CC BY 4.0 标注亦保留在原始元数据中。真实孔阵列板由 Johannes Hinrichs / CodeFHD 的 OptiCore 离线生成，原始 GPL-3.0-or-later 源码、许可和复现参数随素材保存，板件采用相同许可；不据此改变其他项目代码或素材的许可。逐件用途、比例适配及许可边界见 `assets/downloads/optical_reconstruction/README.md`。

考古场景的陶片来自 **Incised Pottery Sherd / Florida Public Archaeology Network (FPAN)**（https://sketchfab.com/3d-models/incised-pottery-sherd-d0f4ee864d9749da8cc095f7a794e6fc），骨骼来自 **Cow Bone .::RAWscan::. / Andrea Spognetta (Spogna)**（https://sketchfab.com/3d-models/cow-bone-rawscan-675694971dcb44e09f32353604a7a01d），经 Objaverse/Ai2 获取，均按 CC BY 4.0 保留作者、来源、许可与修改说明。这些是教学场景中组合的扫描样件，不代表同一遗址的出土组合；统一缩放适配训练包络，不推定实物原始尺度。原始 GLB、官方许可元数据与使用说明保存在 `assets/downloads/dig_reconstruction/`。光学与考古场景复用的 Poly Haven 桌台、工具、土壤及其他 PBR 素材继续适用 CC0；其既有来源记录保持有效。

2026-10-23 第三批素材重构：本段取代上文对 `control_panel`、`connector` 当前派生资产“全部原创、统一 CC0”的描述。控制旋钮来自 **Knob (2021) / emaitee，CC BY 4.0**；电位器和铝型材盒来自 **Adafruit CAD Parts / Adafruit Industries，MIT**。原始 STEP、旋钮 GLB、许可原文和固定版本来源记录保存在 `assets/downloads/control_panel_reconstruction/`。连接器与控制面板共用这一份 Adafruit 2230 CAD，不另存重复源文件；P/S 是以成熟壳体适配的四接点教学接口，新增针、孔、绝缘件与定位键，不是 Adafruit 在售连接器或厂家认证的接合副。具体改动见 `assets/downloads/connector_reconstruction/README.md`。两场景已有 Poly Haven 工作台、仪表、工具和 PBR 材质继续按 CC0 使用。

本批还仅补换考古场景的 STAY 测站与三脚架。**Total Station / makercommons** 经 Objaverse/Ai2 获取，按原页面 **CC BY 4.0** 署名；**Tripod / Artec 3D** 采用官方扫描 OBJ。Artec 当前网页标注 CC BY 4.0，而下载包内 `license.txt` 标注 CC BY 3.0，项目保留两份证据并按随包 CC BY 3.0 保守署名。该三脚架原包没有纹理图；网格减面、移除扫描器 U 架、添加仪器转接盘及材质赋值均明确记录，不称其为完整摄影测量 PBR 素材。来源、原始许可及适配变换见 `assets/downloads/dig_reconstruction/LICENSES.md`、`artec_tripod_source.json` 与 `stay_fit.json`。品牌标记来自原模型，不表示品牌认可。

2026-10-23 第四批素材重构：本段取代上文对 `blocks` 与 `drone_bench` 当前派生资产“全部原创、统一 CC0”的描述。积木 A/B 与 BASE 采用 **LDraw Parts Library 的 3001 / 3867**，保留 James Jessiman 及各依赖文件作者的署名、原始头部和历史记录；本批保留的 25 个几何 DAT 均标注 **CC BY 4.0**。经固定版本 Pybricks 镜像取得，未声称与官方 ZIP 逐字节比对。源几何、许可和有限尺寸适配详见 `assets/downloads/blocks_reconstruction/README.md` 与 `source_receipt.json`。

无人机机架与 5010 电机来自 **PX4/PX4-gazebo-models 的 x500_base / Rudis Laboratories，BSD-3-Clause**，固定提交 `e5997f455e33ec071c7c677fc59a65781de496a4`；该许可来自模型目录本身，原文保存在 `assets/downloads/drone_reconstruction/px4/LICENSE`。电池包体来自 **Tattu battery pack / bhaktaj**，转换盒来自 **Battery Replacement - LIPO / Jayden Downes**，均经 Objaverse/Ai2 取得并按原 Sketchfab API 元数据的 **CC BY 4.0** 保留署名。两块等比缩放包体与下壳组合为教学电池盒；移除独立长引线/插头，新增底轨、接点和承托，不代表厂家在售组合、原始容量或原始实物尺寸。GUARD 复用第三批 emaitee 旋钮来源，继续适用 CC BY 4.0；固定轴座与旋转件分开。逐项来源与修改见 `assets/downloads/drone_reconstruction/README.md`。两场景复用的 Poly Haven 工作台、工具、仪表及材质继续按 CC0 使用，既有共享文件保持原内容。

2026-10-23 第五批素材重构：本段取代上文对 `engine_bay` 与 `cnc_toolchange` 当前派生资产“全部原创、统一 CC0”的描述。发动机采用 **Three Cylinder Motorcycle Engine / Jamie Hamel-Smith**；火花塞采用 **Spark Plug / mr.barbados**；CLAMP 与 TENSIONER 采用 **Inbus Screw, bolt. imbus / YouniqueĪdeaStudio**；CONN 采用 **Threaded Connector 001 / Arrel** 的完整母端半件。四个源模型均经 Objaverse/Ai2 获取，各自 Sketchfab API 元数据确认 **CC BY 4.0**，原始 GLB、署名、许可原文和改动说明保存在 `assets/downloads/engine_reconstruction/`。源零件等比适配原教学接口，发动机以检修台形式陈列，不主张来自同一机型或具有原厂配合关系。

CNC 使用 **Toolrack / Shinya.Araki** 与 **CNC Tool Holder Assembly / vincent.leung**，两者均按各自来源的 **CC BY 4.0** 保留署名。前者提供刀架与 V 槽法兰；后者原说明为 HSK Chuck with Tapered Collet & Locknut，本场景只采用装配态的铣刀、ER 筒夹和锁紧螺母，不把其 HSK 本体当作 BT 锥柄。外锥、拉钉与原坐标适配是明确的教学组件，不代表标准合规或厂家认证。来源、保留部件、减面与重建步骤见 `assets/downloads/cnc_reconstruction/README.md`。模式旋钮继续复用 emaitee 的 CC BY 4.0 素材，面板壳体复用 Adafruit 的 MIT CAD；两场景的既有 Poly Haven 素材继续适用 CC0。上述派生素材不适用项目原创几何的 CC0 总括条款。

2026-10-23 第六批素材重构：本段取代上文对 `dive_fillstation` 与 `infusion_ward` 当前派生资产“全部原创、统一 CC0”的描述。潜水充装训练站使用 **Oxygen Cylinder / Alexander Troianovskyi**、**2Piece-ball-valve-BSP-female / Freek de With** 和 **Pressure gauge / takeboncog**。输液设备训练台使用 **IV Supplies / Ethan Cragun**、**IV Stand / teeart**、**Medical Cart / NicolasVB**、**medical monitor / brodys_arts** 和 **Bomba de Infusión contec 750 / Nataliatorres777**。这些源模型均经 Objaverse/Ai2 获取，按各自 Sketchfab 元数据记录的 **CC BY 4.0** 保留署名；原始模型、来源元数据、许可及具体适配说明分别保存在 `assets/downloads/dive_reconstruction/` 与 `assets/downloads/infusion_reconstruction/`。源模型没有原始纹理的部分，新增材质不称为原始 PBR。

气瓶、通用阀门和接头组合用于原合同的无压训练，不代表潜水充装设备或 DIN 接口认证。输液泵源门体及固定壳体分别复用，泵盒内部载体、导向结构、训练标签与三通旋塞属于明确记录的项目适配，不代表原厂耗材配合或临床功能。外部源模型及其派生件不适用项目原创几何的 CC0 总括条款；既有共享材质继续按原许可使用。品牌标记来自源素材，不表示品牌方认可。
