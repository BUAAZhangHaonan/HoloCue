# SOURCES — 新场景「发动机维修工位」素材（engine_round）

下载时间：2026-09-17 16:20–16:26 (+0800)
执行方式：复用项目下载器 `scripts/assets/download_polyhaven.py` 的
`fetch`/`download_model`/`md5` 逻辑（import 后仅重定向输出目录到本目录），
全部文件经 PolyHaven API 提供的 md5 校验通过（0 失败），
机器日志见同目录 `polyhaven_download_log.json`（155 条记录）。
下载后已将脚本强制添加的 `models/` 层级抹平：`<cat>/<asset_id>/…`。

## 许可

- PolyHaven（模型 + HDRI）：**CC0 1.0 公共领域**（https://polyhaven.com/license）。
  全部模型与 HDRI 均来自 https://polyhaven.com ，API https://api.polyhaven.com 。
- 本目录未包含任何需要登录下载的来源（Sketchfab 登录下载已按约束排除）。
- 服务器 4028 `/home/g203-4028/Models`：只读检查，仅含 LLM/VLM checkpoint
  （GLM/Qwen/InternVL 等），`find` 未发现任何 glb/gltf/fbx/obj/blend，无可复制素材。

## engine/（发动机本体候选 —— 无现成整机，见文末结论）

| 本地路径 | 内容 | 来源 | 许可 | 面数 | 包围盒 m | 材质 |
|---|---|---|---|---|---|---|
| `engine/portable_generator/` | 便携发电机（含小型发动机形态，最接近的现成"发动机体"） | https://polyhaven.com/a/portable_generator | CC0 | 26,419 | 0.82×0.58×0.56 | PBR 贴图(diff/nor/arm) |
| `engine/modular_pipes/` | 模块化金属/PVC 管件套装（106 个部件，机舱管路/软管布景用；整套摊开，需在 Blender 里取单节） | https://polyhaven.com/a/modular_pipes | CC0 | 94,856(全套) | 4.19×2.44×0.46(整套) | PBR 贴图(metal/pvc 各一套) |
| `engine/modular_airduct_circular_01/` | 圆形风管/进气管段套装（16 段，可作机舱进气道布景；需取单段） | https://polyhaven.com/a/modular_airduct_circular_01 | CC0 | 14,280(全套) | 4.17×1.32×1.46(整套) | PBR 贴图 |

## tools/（工具）

| 本地路径 | 内容 | 来源 | 许可 | 面数 | 包围盒 m | 材质 |
|---|---|---|---|---|---|---|
| `tools/flathead_screwdriver/` | 一字螺丝刀（参考图中拆软管卡箍的动作件） | https://polyhaven.com/a/flathead_screwdriver | CC0 | 2,300 | 0.03×0.26×0.03 | PBR |
| `tools/screwdrivers_02/` | 螺丝刀对（十字/一字各一） | https://polyhaven.com/a/screwdrivers_02 | CC0 | 3,548 | 0.10×0.03×0.27 | PBR |
| `tools/ratchet_wrench/` | 棘轮扳手（带棘轮头） | https://polyhaven.com/a/ratchet_wrench | CC0 | 8,796 | 0.04×0.25×0.04 | PBR |
| `tools/combination_wrench/` | 梅花/开口双头扳手 | https://polyhaven.com/a/combination_wrench | CC0 | 1,986 | 0.06×0.02×0.34 | PBR |
| `tools/adjustable_wrench/` | 活动扳手 | https://polyhaven.com/a/adjustable_wrench | CC0 | 5,390 | 0.07×0.25×0.03 | PBR |
| `tools/pliers/` | 钢丝钳 | https://polyhaven.com/a/pliers | CC0 | 4,540 | 0.06×0.18×0.02 | PBR |
| `tools/tongue_groove_pliers/` | 水泵钳（拆卡箍常用） | https://polyhaven.com/a/tongue_groove_pliers | CC0 | 2,694 | 0.06×0.01×0.24 | PBR |
| `tools/metal_toolbox/` | 金属手提工具箱（开合两态 6 部件） | https://polyhaven.com/a/metal_toolbox | CC0 | 14,228 | 0.40×0.31×0.27 | PBR |
| `tools/metal_tool_chest/` | 金属工具柜（7 抽屉） | https://polyhaven.com/a/metal_tool_chest | CC0 | 13,360 | 0.69×0.65×0.41 | PBR |
| `tools/tool_cart/` | 工具车（多层带轮） | https://polyhaven.com/a/tool_cart | CC0 | 29,394 | 1.27×0.97×0.75 | PBR |
| `tools/bench_vice_01/` | 台虎钳（装工具桌用） | https://polyhaven.com/a/bench_vice_01 | CC0 | 2,864 | 0.20×0.29×0.40 | PBR |

## garage/（车库环境件 + HDRI）

| 本地路径 | 内容 | 来源 | 许可 | 面数 | 包围盒 m | 材质 |
|---|---|---|---|---|---|---|
| `garage/steel_frame_shelves_02/` | 钢架货架（单体，4 层） | https://polyhaven.com/a/steel_frame_shelves_02 | CC0 | 4,348 | 0.59×2.14×0.50 | PBR |
| `garage/steel_frame_shelves_01/` | 钢架货架全套（多节摊开，需切割取单节） | https://polyhaven.com/a/steel_frame_shelves_01 | CC0 | 4,348 | 10.97×21.41×5.02(整套) | PBR |
| `garage/WoodenTable_03/` | 木桌（工具桌替身；PolyHaven 无专用 workbench） | https://polyhaven.com/a/WoodenTable_03 | CC0 | 2,298 | 1.33×0.83×0.58 | PBR |
| `garage/oil_tin/` | 机油铁罐 | https://polyhaven.com/a/oil_tin | CC0 | 2,834 | 0.12×0.21×0.15 | PBR |
| `garage/small_oil_can_01/` | 小油壶（长嘴） | https://polyhaven.com/a/small_oil_can_01 | CC0 | 16,746 | 0.27×0.24×0.10 | PBR |
| `garage/lubricant_spray/` | 润滑喷剂罐 | https://polyhaven.com/a/lubricant_spray | CC0 | 5,476 | 0.07×0.17×0.07 | PBR |
| `garage/hanging_industrial_lamp/` | 工业吊灯（带发光贴图） | https://polyhaven.com/a/hanging_industrial_lamp | CC0 | 9,530 | 0.55×1.36×0.55 | PBR(含 emissive) |
| `garage/caged_hanging_light/` | 网罩吊工作灯（含垂线，含 emissive） | https://polyhaven.com/a/caged_hanging_light | CC0 | 22,893 | 1.16×0.75×0.32 | PBR(含 emissive) |
| `garage/mounted_fluorescent_lights/` | 吸顶荧光灯排（14 管，含 emissive） | https://polyhaven.com/a/mounted_fluorescent_lights | CC0 | 17,820 | 0.91×0.04×0.65 | PBR(含 emission) |
| `garage/old_tyre/` | 旧轮胎 | https://polyhaven.com/a/old_tyre | CC0 | 2,880 | 0.60×0.60×0.17 | PBR |
| `garage/rusted_wheel_rim_01/` | 锈蚀轮毂 | https://polyhaven.com/a/rusted_wheel_rim_01 | CC0 | 16,440 | 0.41×0.41×0.15 | PBR |
| `garage/old_military_compressor/` | 老式空压机（带电机/泵） | https://polyhaven.com/a/old_military_compressor | CC0 | 79,042 | 0.60×1.18×1.68 | PBR |
| `garage/portable_welding_cart/` | 焊接车（气瓶+焊机） | https://polyhaven.com/a/portable_welding_cart | CC0 | 29,418 | 0.84×1.56×0.66 | PBR |
| `garage/industrial_storage_cart/` | 工业置物推车 | https://polyhaven.com/a/industrial_storage_cart | CC0 | 18,902 | 1.60×1.38×1.10 | PBR |
| `garage/ladder_sectioned_01/` | 分节梯子（4 节） | https://polyhaven.com/a/ladder_sectioned_01 | CC0 | 29,140 | 0.66×2.14×0.18 | PBR |
| `garage/autoshop_01_1k.hdr` | 修车行 HDRI（1k，RADIANCE .hdr，1.6MB） | https://polyhaven.com/a/autoshop_01 | CC0 | — | — | 32bit HDR |
| `garage/garage_1k.hdr` | 车库 HDRI（1k，RADIANCE .hdr，1.6MB） | https://polyhaven.com/a/garage | CC0 | — | — | 32bit HDR |

## 验证记录

- 加载器：`.venv/bin/python` + trimesh 4.12.2，`trimesh.load(path, force='scene')`。
- 29/29 模型加载成功，全部为 glTF 2.0 + PBRMaterial 且每个几何体都带贴图
  （diff/nor_gl/arm 1k JPG）。面数与包围盒见上表（单位米）。
- HDRI 为标准 `#?RADIANCE` 头的 .hdr，可直接被 Blender/three.js 读取。

## 搜索结论（发动机整机是否存在现成开放许可素材）

- PolyHaven：521 个模型全量检索 engine/car/vehicle/motor/piston 等关键词，
  **无汽车发动机整机**（最接近 portable_generator）。
- Kenney Car Kit（CC0，https://kenney.nl/assets/car-kit ）：已下载解包检查，
  45 个文件全是整车/车轮/碎片件，**无发动机部件**，故未收入本目录。
- Quaternius（CC0，https://quaternius.com ）：所有包为整车/角色/场景，
  无 engine/garage 内容。
- Poly Pizza（CC0/CC-BY 聚合）：检索 "engine / car engine / v8" 仅
  "Space engine"、"Sci Fi Engine" 等低多边形科幻件，与 EA888 写实风格不符。
- 4028 `/home/g203-4028/Models`：仅 LLM/VLM checkpoint，无任何 3D 网格文件。
- **结论：横置直列四缸发动机本体（含机舱/发动机架、进气歧管、卡箍、皮带轮）
  需要按参考图在 Blender 手工建模**；上表管件/风管素材可作机舱细节补充。
