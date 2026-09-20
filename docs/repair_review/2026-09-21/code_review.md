# HoloCue 本批独立代码审查

- 审查代理：`/root/repair_code_review`（实际独立 SubAgent 会话；主代理 `/root`）。
- 日期：2026-09-20；方式：SSH `4029`，只读源码、diff、已有执行记录及文件哈希。
- 仓库：`/home/hdd3/zhanghaonan/projects/holocue`。
- 实测 HEAD：`55cfe656182411965d0f12d8a5ff92b2d885535f`。
- 记录目录：`runs/simulation/repair_review_20260920_25bcc909`。
- `pytest_command/execution.json` 的 source_before/source_after digest 均为 `2ef99b6626387225afacc10502e6d3b83e1359a0c7e528d7036e54f683002366`，算法 `sha256-path-size-content-v1`。已逐文件重算其清单内容 SHA-256，与当前磁盘无不符。本代理未独立重算聚合 digest。

## 结论与问题（按严重程度）

未发现 P1/P2 级代码问题；存在一项 P3 断言保留缺口。当前读取器替换保留主要几何、材质和存储法线断言，不能表述为所有旧结构断言逐项完全保留。

**P3：GLB 总长度严格检查被删除。** `tests/test_asset_normals.py:11-16` 的成熟库读取替换移除了原 `header.length == len(data)` 断言。本地已安装的 `pygltflib.load_from_bytes` 只按声明长度遍历；`trimesh.exchange.gltf.load_glb` 在不足 8 字节下一 chunk header 时退出，不核对声明总长度与真实文件长度。因此合法 GLB 后附加不足 8 字节数据时，两条读取路径均可能继续成功，而旧断言会失败。依据为两库的实际源码阅读；未运行修改文件复现。建议保留这项容器完整性断言，仍由成熟库处理 JSON、accessor 与 geometry。该项不表示本批现有 GLB 已损坏。

补充接口核对：已完整读安装版 `pygltflib/validator.py`，公开 validate 仅检查解码后的 accessor/sparse/animation/mesh/bufferView，不能验证已丢弃的头部 length；file-object 加载先 `read()` 全文件，游标检查不等价。Trimesh 也会读走不足 8 字节尾巴后退出，EOF 游标不足以恢复严格长度约束。未发现两库现有公开读取接口可替代此项独立头部检查。旧 non-sparse 断言准确位置为基准 HEAD `tests/test_asset_normals.py:26`，新 pygltflib accessor 元数据可用 `.sparse is None` 保留它，无需手写 accessor 偏移。

## 已核对的结果

- `exported_normals` 使用 Trimesh 的原始构造参数，尚未构建/处理 mesh；库源码直接把 NORMAL accessor 数组传到 `vertex_normals`，不重算法线。新代码保留 float32、VEC3/同 POSITION 形状、节点唯一性并增加有限值检查；新增测试覆盖真实存储值、顺序、局部坐标与节点旋转分离、缺少 NORMAL、多个节点及独立数组。旧固定 `byteStride == 12` 限制改为成熟库实际解码 stride，是能力扩展。旧通用 accessor 的 non-sparse 拒绝断言不再显式存在；新增测试没有覆盖 sparse，这不应被表述为已验证 sparse 支持。
- `test_asset_normals` 保留圆柱 80+80 三角形、端面/侧面顶点分离、半径方向法线、共享顶点法线、PBR 值、UV 与嵌入纹理检查。
- `validate_model_dir` 保留模型类型、tokenizer 存在、分片存在、目录逃逸与截断拒绝边界；`safe_open`/`get_slice().get_shape()` 为延迟元数据路径，无张量实体加载调用。新增非空分片、重复 tensor、index 与实际 tensor-to-shard 精确一致检查；没有把 metadata/length 检查包装成内容哈希验证。未读取或运行真实模型。
- quaternion 有限性由 `Strict` 的 `allow_inf_nan=False` 提供，单位范数由新 validator 提供。仅 optical scene JSON 改为指定旋转；新场景枚举测试锁定其他场景恒等旋转。contract 测试对新字段作兼容后，其余对象、相机和任务字段仍作完整比较。
- `git diff --name-only -- src/holocue/modeling.py tests/fixtures` 无输出：本批建模源码与固定 fixture 未改。CLAMP、L1/L2 的几何断言、数值阈值、fixture hash、允许节点集合没有修改；本批测试改动是法线读取器及环境字段比较适配。标准 GLB 文件确有重建变化，不应称二进制未改。
- `build_all.sh` 先真实生成标准资产，再导出 payload，再构建 Blender；`build_simulation_assets` 分开记录 requested/built scene IDs、built assets 与磁盘 inventory。已有 `assets.provenance.json` 为 12 请求/12 完成、76 built assets/76 inventory、complete=true。
- 已读取 12 份 `build_provenance/*.json` 并核对每份 payload、输入源码、资产、blend、render 的内容 SHA-256，全部与当前磁盘一致且都有 render 记录。Blender 构建入口在导入前重新核对 payload 中的 source/assets，报告真实保存后的 blend 和实际渲染文件哈希，未发现只写清单冒充重建的路径。
- mirror 审计使用单一真实会话的初始/完成快照、生产 SceneRenderer、独立 before/after 客户端，锁定成对相机和 mesh/material 数据；报告明确将视觉验收标为 pending。反射方向函数也明确只是估算，实际图像应由独立视觉审查判断。

## 实际读取范围

完整 diff：`pyproject.toml`、`requirements-simulation.txt`、`schemas/scene.schema.json`、`scripts/ops/serve_model.sh`、`scripts/ops/validate_model_dir.py`、`scripts/scenes/build_all.sh`、`scripts/scenes/build_blender_scene.py`、`scripts/scenes/build_simulation_assets.py`、`scripts/scenes/export_blender_payload.py`、`src/holocue/models.py`、`src/holocue/viewer_scene.py`、`tests/test_asset_normals.py`、`tests/test_engine_clamp.py`、`tests/test_optical_lens_seat.py`、`tests/test_panel_optical_mounts.py`、`scenes/optical_bench/scene.json`。

新增文件全文：`src/holocue/glb_attributes.py`、`tests/test_glb_attributes.py`、`tests/test_model_directory_reader.py`、`tests/test_environment_orientation.py`、`scripts/scenes/build_provenance.py`、`scripts/tests/audit_mirror_environment.py`。

额外当前上下文：`AGENTS.md`；`models.py` 的 Strict/Pose/RenderHints；三个构建入口全文；`test_asset_normals.py` 全文；CLAMP 测试 85–260 行；L1/L2 测试 45–153 行；panel/optical 测试 1–108 行。库源码：本环境 `trimesh/exchange/gltf/__init__.py` 的 GLB 头/chunk、accessor stride、NORMAL 装配部分；`pygltflib/__init__.py` 的二进制加载部分。已有记录：pytest execution、assets provenance、12 份 build provenance。

## 未覆盖项

本代理没有运行模型、构建、渲染、pytest 或有序运动测试，也没有修改远端代码；431 pytest 与 18 有序运动结果不是本代理重新执行所得。仅核对已有 pytest 执行记录 returncode=0 和来源一致性。未操作真实 UI、观察渲染图片、验证 HDR 方向的最终视觉效果，原生检查由主线程及视觉代理负责。构建 provenance 的局部 source 清单不是完整依赖闭包（例如 camera/assets/spatial 模块不在局部清单）；本批额外依赖完整 pytest source 清单的当前一致性，不能将单独局部 provenance 当成未来任意改动下完整可复现构建证明。
