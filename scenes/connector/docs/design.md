# `connector` 场景设计（初代最小场景）

初代三场景之一：插头空间对准，承载 insertion 锚点与 ghost_motion 演示的最小用例。共同协议见 `docs/05_场景与验收协议.md`。

- 初始指令：演示把 P 插进 S，插好后再检查 C。
- 对象（3）：P 蓝色插头（point/insert/inspect_back，insertion 锚点在插座 S 口面）、S 目标插座（point/inspect_back）、C 备用模块（point/inspect_back）。
- 几何：trimesh 基元族（`scripts/assets/generate_assets.py`），共享池 `assets/meshes/common/`；module 与 control_panel 复用。
- 测试绑定：`tests/test_core.py` 姿态动画不变式；`examples/replay.json` 回放夹具。
- live 绑定：`scripts/live_checks/live_smoke.py`。
- 现行数值以 `scenes/connector/scene.json` 为准。
