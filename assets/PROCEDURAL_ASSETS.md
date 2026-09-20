# 参数化场景资产

本包的 76 个 GLB 由 `src/holocue/modeling.py` 与 `scripts/scenes/build_simulation_assets.py` 生成。资产包括 64 个场景对象和 12 份工作环境。模型使用尺寸化实体、圆角、空腔、螺纹示意、孔位、支架和内嵌文字纹理。

使用 CadQuery 构造实体，使用 Trimesh 输出 glTF。标签纹理由本地字体渲染为图像后嵌入模型。压缩包包含生成的图像，字体文件保留在运行环境中。

本次打包没有引入第三方下载模型。已有仓库资产继续保留各自的来源与许可记录。项目发布时，按照项目确定的许可发布本包生成内容。

逐文件 SHA256 与路径保存在迭代包的 `MANIFEST.json`，几何统计保存在 `evidence/independent_check.json`。
