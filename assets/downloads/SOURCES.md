# 外部素材来源与许可记录

所有外部素材仅存放于本目录 `assets/downloads/`,加工后的单文件 GLB 位于 `assets/meshes/env/`。

## PolyHaven(https://polyhaven.com)

- 许可:CC0 1.0 Universal(公有领域贡献,可商用、可修改、无需署名)。
- 下载时间:2026-09-17。
- 下载方式:`scripts/assets_v2/download_polyhaven.py`(经 api.polyhaven.com 获取文件清单与 md5,逐文件校验后落盘)。
- 逐文件 md5 校验记录:`polyhaven/polyhaven_download_log.json`(241 个条目,全部 `md5_ok: true`)。
- 模型目录:`polyhaven/models/<id>/`(.gltf + .bin + 1k jpg 纹理,保持原始相对路径结构)。
- 纹理目录:`polyhaven/textures/<id>/`(1k jpg 贴图)。
- 零售来源确认:api.polyhaven.com 返回的每个 asset 的 `license` 字段为 `CC0`。

### 已下载模型(26)

worn_metal_rack, modular_electric_cables, circuit_board, security_camera_01,
metal_toolbox, screwdrivers_02, pliers, bench_vice_01, magnifying_glass_01, retro_multimeter,
cardboard_box_01, plastic_crate_01, plastic_crate_02, wooden_crate_02, Barrel_02, cement_bag,
hand_truck, steel_frame_shelves_02, desk_lamp_arm_01, binder_notebook,
trowel_01, rusted_spade_01, stone_01, rock_07, ceramic_pot, wooden_crate_01

### 已下载纹理(13)

metal_plate_02, factory_wall, hangar_concrete_floor, rubber_tiles, wood_table_001,
concrete_floor_worn_001, metal_plate, rough_linen, marble_01,
excavated_soil_wall, dirt, gravelly_sand, hessian_230

## 加工产物

`assets/meshes/env/<id>.glb` 由 `scripts/assets_v2/process_props.py`(Blender 3.1.2)从上述原始文件导出,纹理内嵌,几何未修改(仅单位确认与清理摄像机/灯光),尺寸/面数清单见 `runs/scene_v2/prop_inventory.json`。

## 项目内自有资产

`assets/meshes/`(v1)与 `assets/meshes/<scene>/`(v2 交互对象)为程序化生成的原创资产,见 `assets/ASSET_LICENSE.md`(CC0)。
