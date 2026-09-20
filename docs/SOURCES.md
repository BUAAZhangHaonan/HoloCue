# 已核查的实现资料

代码审阅基准为 `BUAAZhangHaonan/HoloCue` 的 `8ac969fc2adbd5095720f8b1c03c5683b4b1e3b3` 提交。读取范围覆盖场景配置、场景构建入口、任务协议、状态持久化、模型请求、显示投影、网页代码与现有测试。

| 资料 | 本包使用的接口或概念 |
|---|---|
| [Viser Scene API](https://viser.studio/main/api/core/scene_api/) | 客户端场景、标准 GLB、Gaussian splats、坐标层次与光照 |
| [Viser Scene Handles](https://viser.studio/main/api/handles/scene_handles/) | set_gaussians 同步更新中心、协方差、颜色与不透明度 |
| [Viser Client Handles](https://viser.studio/main/api/handles/client_handles/) | 客户端隔离、消息组更新与相机控制 |
| [Viser Events](https://viser.studio/main/api/advanced/events/) | 区分用户事件与服务端产生的控件更新 |
| [SciPy Rotation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.transform.Rotation.html) | 四元数、旋转复合、逆变换与向量变换 |
| [Trimesh glTF](https://trimesh.org/trimesh.exchange.gltf.html) | 使用成熟库读取与输出标准 glTF |
| [CadQuery Introduction](https://cadquery.readthedocs.io/en/latest/intro.html) | 尺寸驱动的实体建模与几何构造 |

Viser 依赖固定为 1.1.1。官方 main 文档会持续更新，服务器应同时核对已安装版本的函数签名。Blender 脚本围绕现有 3.1 系列环境编写，具体兼容性由原生执行验证。
