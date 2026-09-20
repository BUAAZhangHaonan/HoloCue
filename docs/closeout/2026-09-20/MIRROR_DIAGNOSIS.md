# optical_bench M 镜面只读诊断

现有证据最支持：Viser 正常使用已加载的 studio 环境，但当前 M 正面视角反射的是该环境的黑色幕布，0.1 环境强度进一步压暗；metal=0.95、roughness=0.08 使表面主要呈现这个暗的窄角度反射。没有发现缺环境映射、HDR 资源失败、协议错配或背面朝向的证据。尚未改动光照做受控 A/B，因此这不是对所有像素成因的完整因果分解。

已直接看原始两图，也用新独立 CPU 浏览器客户端打开真实已完成会话 `94a59abd6e444faba971d1d0a6bf81a0`，复现相同镜面。中心矩形 `[550,350,730,550]` 内，旧 Viser 和新客户端平均 RGB 均为 `[3,4.07036,6]`；旧 Blender 为 `[167.14,178.51,185.06]`。这是近黑现象的描述，不是跨渲染器质量分数。截图原样保留在 `input_images/` 和 `current_client_M_detail.png`。

| 证据层 | 实际结果 |
|---|---|
| 生产配置 | `client.scene.configure_environment_map('studio', background=False, environment_intensity=.1)`；官方默认直射灯开启，阴影关闭 |
| 包/服务身份 | 实际运行 Viser 1.1.1，viewer PID1263268 使用生产 `.venv-simulation`；HTTP 实际 HTML SHA `d7a86b58a884879e1e6f09382d405bb69e761afe9fc8c1fdbe5eea6a787230e7`，与安装 build 相同 |
| 实际 WebSocket | 收到 30,343 字节 HDR JPEG；SHA `e03b8f898562515714bab61fee0dd1e09c880e7b06c979148fc1eaca52680b7a`，与安装 studio 预设逐字节相同；实际强度 .1、旋转单位四元数 |
| 实际纹理 | `scene.environment` 非空，1024×512 HalfFloat render-target texture、linear-sRGB、EquirectangularReflectionMapping；强度 .1、旋转 0、canvas opacity 1；等待后仍相同 |
| 实际镜面材质 | `M0001_mirror_face` / `MeshStandardMaterial`，metalness .95、roughness .08、envMapIntensity 1、无 normalMap、可见；`material.envMap=null` 表示使用 scene.environment，不能据此判断环境缺失 |
| 实际浏览器 | SwiftShader 软件渲染、空 CUDA；无页面错误、无 HTTP 请求失败、无 HDR JPEG 加载错误。软件渲染提示和 THREE.Clock 弃用提示保留 |
| 原会话 | 前后 state 完全一致、revision 22 未变；只有新客户端自身的 GUI 观察操作和 camera 消息，没有任务提交/暂停/完成/恢复操作 |

主要环境 API、App、HDR loader、GLB loader 与 wheel RECORD 相同；`_messages.py` 与 build 是项目既有补丁，前者与仓库补丁相同，后者是上述已接受的实际 bundle。没有将磁盘源码配置冒充运行时证明。

实际 GLB SHA `eaec11075faa4d129325f7dbb0cf4beaf9c3d89792179d13b5b86c3747bc3ddf`。结合该 GLB 的64个正面三角、浏览器实际 mesh.matrixWorld 和相机位置，正面中心朝向相机点积为 .944989871。中心镜面反射方向（Three 世界坐标）为 `[.816693169,-.327082075,-.475425688]`，映射到未旋转环境的 equirect UV `[.416096713,.393934641]`，对应 JPEG `(426,310)`，SDR 底图 RGB `[14,13,18]`。64个正面三角质心也全部落在暗幕区域，连同中心65点的各通道最小值 `[3,3,3]`，最大 `[16,17,20]`，平均约 `[10.05,9.95,13.03]`。完整方向和三角索引在 `reflection_direction.json`；原始 HDR 字节在 `websocket_environment_00.jpg`。

这里的像素采样是 HDR JPEG 的 SDR 底层，不是 gainmap 解码后的辐射值，也没有重建 PMREM 或最终 shader。它是“当前反射方向指向黑幕”的直接方向证据，不能当作精确最终亮度预测。低 roughness 表示近镜面反射，本身不是不支持的材质；高 metalness 会削弱漫反射。官方 MeshStandardMaterial 使用环境贴图进行 PBR 反射，scene.environment 会供未显式绑定 envMap 的物理材质使用。[MeshStandardMaterial 官方文档](https://threejs.org/docs/pages/MeshStandardMaterial.html)；[Scene 官方文档](https://threejs.org/docs/pages/Scene.html)。

旧 Blender 图并非与 Viser 共用这套灯光：场景构建源码设定世界颜色 `(.70,.76,.82)`、强度 `.45` 和三个 AREA softbox，使用 Cycles。归档图中已经呈现明亮反射；本诊断只读了该归档及构建源码，没有重新读取运行中的 Blender 内部灯光状态，也没有启动 Blender。不能以两个不同照明/反射管线的外观差异推断 GLB 材质丢失。

最小建议：如果目标是让默认 M 正面观察能读出镜面材质，先做一个**仅 optical_bench、新客户端场景范围**的候选，保持 metal/roughness、物体、相机、动作和 `.1` 强度不变，只通过官方 `configure_environment_map(..., environment_wxyz=...)` 旋转现有 studio 环境，让上述实际反射方向落到预设的宽灰白背景纸或软箱边缘，而不是当前黑幕。可先以底图灰白背景纸约 `(u=.25,v=.45)` 为方向目标，由场景坐标转换计算固定旋转；该目标和参数尚未渲染验证，不应直接宣称修复。这样有明确几何依据，且只改变一个官方支持的环境方向参数。官方 1.1.1 支持独立设置环境旋转、强度和背景显示；HDR loader 确实将它们应用到 scene.environment。[Viser Scene API](https://viser.studio/main/api/core/scene_api/)；[v1.1.1 官方 HDR loader](https://raw.githubusercontent.com/viser-project/viser/v1.1.1/src/viser/client/src/HDRJPGEnvironment.tsx)。

候选复验范围限定为 optical：M 初始姿态与完成 -15° 后的工作区/目标特写/结构检查，以及 L1/L2/TARGET 的白色标识、镜片和金属边框对比度；复核环境消息/资源成功、会话不变。先完成这一次固定方向的对照，再决定是否确有必要微调强度。无需降低 metal、全局改灯、修改官方客户端、增加 Three/shadow/custom renderer；也不能把环境贴图反射称为对场景内真实物体的光线追踪镜像。当前没有实施任何建议。

命令、退出、资源与文件摘要见 `sealed_evidence.json`。首次浏览器观察因原生 select 选择器不适配 Mantine 超时，且当时诊断解码器误按普通 msgpack 读取官方 hybrid 帧；两者均为诊断脚本问题，原证据保留在 `attempt_1/`。随后改用项目已有 combobox 流程与官方 hybrid zstd 布局，真实观察退出0。反射脚本首次按 geometry 名称查找失败，随后按 GLB node→geometry 映射读取，失败脚本与日志也保留；这些没有触碰生产或旧会话。
