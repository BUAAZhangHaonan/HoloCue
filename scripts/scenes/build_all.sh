#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
export TMPDIR="$PWD/.work/tmp"
export TMP="$TMPDIR"
export TEMP="$TMPDIR"
export XDG_CACHE_HOME="$PWD/.work/cache"
export PIP_CACHE_DIR="$PWD/.work/cache/pip"
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.work/browsers"
export PYTHONPYCACHEPREFIX="$PWD/.work/pycache"
mkdir -p "$TMPDIR" "$XDG_CACHE_HOME" "$PYTHONPYCACHEPREFIX"
: "${BLENDER_BIN:?Set BLENDER_BIN to the installed Blender executable}"
test -x "$BLENDER_BIN"
APP_PYTHON="${APP_PYTHON:-$PWD/.venv-simulation/bin/python}"
test -x "$APP_PYTHON"
test -f scripts/guard/resource_guard.py
"$APP_PYTHON" scripts/guard/resource_guard.py --rss-limit-gb 12 --log "${RUN_DIR:-runs/simulation}/payload_resources.jsonl" --execute -- \
  "$APP_PYTHON" scripts/scenes/export_blender_payload.py
for SCENE_FILE in scenes/*/scene.json; do
  SCENE_DIR="$(dirname "$SCENE_FILE")"
  SCENE="$(basename "$SCENE_DIR")"
  [[ "$SCENE" == _* ]] && continue
  "$APP_PYTHON" scripts/guard/resource_guard.py --rss-limit-gb 12 --log "${RUN_DIR:-runs/simulation}/blender_${SCENE}_resources.jsonl" --execute -- \
    "$BLENDER_BIN" -b -t 4 --python-exit-code 1 --python scripts/scenes/build_blender_scene.py -- --scene "$SCENE" --render
done
