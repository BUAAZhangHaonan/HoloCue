# 固定资产来源与许可

本包的九组 GLB 和 OBJ 几何（现位于 `assets/meshes/common/`）、Gaussian 预览采样池由本次交付的生成脚本创建，使用原创基础几何组合。可在该项目中使用、修改和重新发布；固定资产按 CC0 1.0 提供。

这些是通用旋钮、模块、插接件和积木造型，不对应真实商业器件或品牌 CAD。GLB 包含顶点颜色，OBJ 提供简便的几何导入。几何单位是米，坐标为右手系、Z 轴向上。

Gaussian NPZ 是可重复的几何采样池，用于测试数量变化与接口。光学拟合与标定由全息后端提供。外部论文代码和模型权重均未打入本包，使用时遵循对应项目许可。

2026-09-17 v2 扩展（2026-09-18 套件化迁移）:五组扩展场景的交互对象位于 `scenes/server_rack/meshes/`、`scenes/drone_bench/meshes/`、`scenes/shelf_picking/meshes/`、`scenes/optical_bench/meshes/`、`scenes/dig_site/meshes/`,程序化环境件位于各套件的 `scenes/<id>/meshes/env/` 子目录,均为本项目原创生成,按 CC0 1.0 提供;PolyHaven 下载素材与其转换件（共享池 `assets/meshes/env/`）的来源与许可见 `assets/downloads/SOURCES.md`。

v3 发动机舱复刻轮（2026-09-17）：`assets/raw/engine_round/` 的 29 个 PolyHaven 模型与 2 个 HDRI 均为 CC0，来源/许可/校验见 `assets/raw/engine_round/SOURCES.md` 与同目录 `polyhaven_download_log.json`（155 条 md5 校验；两条 HDRI 的 md5 值为事后按本地文件补记并经 PolyHaven 线上 API 复核，见日志内 md5_note）。`scenes/engine_bay/meshes/` 六个交互对象与 `scenes/engine_bay/meshes/env/engine_*` 三个环境件为本项目程序化原创，同 v1 条款（CC0）。

2026-09-18 v4 新三场景套件:`scenes/cnc_toolchange/`、`scenes/dive_fillstation/`、`scenes/infusion_ward/` 三套件的全部交互对象与环境件（`scenes/cnc_toolchange/meshes/`、`scenes/dive_fillstation/meshes/`、`scenes/infusion_ward/meshes/` 及各自 `env/` 子目录）由各自的 kit builder（`scripts/scenes/build_<scene>.py`，Blender 3.1.2 程序化建模）原创生成，无外部素材引入，同 v1 条款按 CC0 1.0 提供。
