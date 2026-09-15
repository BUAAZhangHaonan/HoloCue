#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
BLENDER_BIN="${BLENDER_BIN:-$(command -v blender || true)}"
[[ -x "$BLENDER_BIN" ]] || { echo 'Set BLENDER_BIN to the existing server Blender executable'; exit 2; }
for SCENE in control_panel connector blocks; do
 .venv/bin/python scripts/resource_guard.py --rss-limit-gb 12 --execute -- "$BLENDER_BIN" -b -t 4 --python scripts/build_blender_scene.py -- --scene "$SCENE" --render
done
