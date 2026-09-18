# 新场景套件检查单（scenes/_template/）

复制本目录为 `scenes/<scene_id>/`（下划线开头目录不进场景清单），按序走完：

1. **提案与三轮审查**（scene_agent/ 流程）：`requirements.md` 章程 → `proposals/<id>_vN.md` →
   research/realism/feasibility 三独立 SubAgent 全 pass 才归档；归档时设计正本移入
   `scenes/<id>/docs/design.md`，评审报告移入 `scenes/<id>/reviews/`。
2. **per-scene builder**：`scripts/scenes/build_<id>.py`，模板参照 `build_server_rack.py` /
   `build_dive_fillstation.py`（LAYOUT 唯一真源 + `from common import *` + kit 校验断言：
   verify_depths / verify_frame / verify_visibility / verify_back_radial / 插入落位）。
   产物：`scenes/<id>/meshes/<OID>.glb`（局部原点）与 `scenes/<id>/meshes/env/<id>_<prop>.glb`。
   经 resource_guard 运行，日志重定向到 `runs/scene_v2/build_<id>.log`。
3. **origin 守卫**：`.venv/bin/python scripts/scenes/check_origins.py <id>` 全 ok；
   特殊原点约定登记进其 KNOWN_CONVENTIONS（口面原点类）。
4. **scene.json 定稿**：builder 的 write_scene_json 产出；相机/深度表 = 评审过的设计值，
   禁止模板值（ortho/grid 须按实测标定）。
5. **官方链**：`bash scripts/scenes/build_all.sh <id>` → `scenes/<id>/blend/<id>.blend`、
   `runs/<id>_blender.png`、`runs/<id>_label_px.json`（resource_guard + Blender 3.1.2 CPU）。
6. **契约校验**：`.venv/bin/python scripts/scenes/check_scene_kit.py` 全 ok
   （配置可载、资产在位、blend/docs/reviews/builder 齐、license 已登记）。
7. **测试**：tests 增补该场景用例（能力表/深度分层/初始指令一致性）；全量 pytest 绿。
8. **live E2E**（按需）：serve_model.sh（物理 GPU 1/2，vLLM 4B）→ run_api.sh →
   `scripts/live_checks/` 新增/扩展场景绑定，原始输出留痕 runs/。
9. **回写**：README 场景清单、`runs/EVIDENCE_INDEX.md` 新章节、
   `assets/ASSET_LICENSE.md` 新段、`MANIFEST.sha256` 重导出（scripts/release/verify_package.py）。
10. **收官门禁**：三份独立 SubAgent 审查 JSON（runtime_safety / interaction_visual[视觉实查] /
    architecture_reproducibility）过 `scripts/release/check_review_gate.py`。
