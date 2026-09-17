#!/usr/bin/env bash
# Official scene build for all scenes (v1 + v2): .blend + annotated render per scene.
# CPU-only, resource-guarded; per-scene .blend + annotated render + origin guard.
set -euo pipefail
cd "$(dirname "$0")/../.."
BLENDER_BIN="${BLENDER_BIN:-$(command -v blender || true)}"
[[ -x "$BLENDER_BIN" ]] || { echo 'Set BLENDER_BIN to the existing server Blender executable'; exit 2; }
SCENES=("$@")
[[ ${#SCENES[@]} -eq 0 ]] && SCENES=(control_panel connector blocks server_rack drone_bench shelf_picking optical_bench dig_site engine_bay)
for SCENE in "${SCENES[@]}"; do
  echo "== $SCENE =="
  .venv/bin/python scripts/guard/resource_guard.py --rss-limit-gb 12 --execute -- \
    "$BLENDER_BIN" -b -t 4 --python scripts/scenes/build_blender_scene.py -- --scene "$SCENE" --render
  .venv/bin/python scripts/scenes/annotate_render.py "$SCENE"
done
.venv/bin/python scripts/scenes/check_origins.py "${SCENES[@]}"
