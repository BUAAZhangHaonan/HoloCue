# `blocks` 场景设计（初代最小场景）

初代三场景之一：积木分步搭建的最小世界，用于验证接口闭环（LLM 决策 → 状态机 → 投影 → DisplayPacket）。共同协议见 `docs/05_场景与验收协议.md`；扩展轮判据见 `docs/09_新场景与任务设计.md`。

- 初始指令：先把 A 放到底板 BASE 上，然后检查 B 的背面。
- 对象（3）：A 黄色积木（point/assemble/inspect_back，placement 锚点在 BASE）、B 蓝色积木（point/assemble/inspect_back）、BASE 绿色底板（point）。
- 几何：trimesh 基元族，`scripts/assets/generate_assets.py` 生成，共享池 `assets/meshes/common/`。
- live 绑定：`scripts/live_checks/live_smoke.py` 与 `live_extended.py` G6（replace 新任务）。
- 现行数值以 `scenes/blocks/scene.json` 为准。
