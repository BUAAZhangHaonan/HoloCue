# `control_panel` 场景设计（初代主场景）

初代三场景之首：旋钮角度操作与背面检查，是状态机、打断-恢复、改参 replace、能力违规等核心用例的主绑定场景。共同协议见 `docs/05_场景与验收协议.md`。

- 初始指令：把 B 逆时针转 30 度，接着检查 C 的背面。
- 对象（3）：A 旋钮 A（point/rotate）、B 旋钮 B（point/rotate，顶部白线为角度指示线）、C 模块 C（point/inspect_back，背面有凸出的黄色定位结构）。
- 几何：trimesh 基元族（`scripts/assets/generate_assets.py`），共享池 `assets/meshes/common/`。
- 测试与回放：`tests/test_core.py` 约 30 处绑定；`examples/replay.json` 与 `examples/display_packet.preview.json`。
- live 绑定：`scripts/live_checks/live_smoke.py`、`live_interrupt.py`、`live_extended.py`（G1–G5、G7）。
- 现行数值以 `scenes/control_panel/scene.json` 为准。
