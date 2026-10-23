#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
if [[ "${1:-}" == "--scene-set" ]]; then
  export HOLOCUE_SCENE_SET="${2:?Specify legacy or reconstructed}"
  shift 2
fi
if [[ $# -ne 0 ]]; then
  echo 'Usage: build_all.sh [--scene-set legacy|reconstructed]' >&2
  exit 2
fi
export TMPDIR="${TMPDIR:-$PWD/.work/tmp}"
export TMP="${TMP:-$TMPDIR}"
export TEMP="${TEMP:-$TMPDIR}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$PWD/.work/cache}"
export PIP_CACHE_DIR="${PIP_CACHE_DIR:-$XDG_CACHE_HOME/pip}"
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$PWD/.work/browsers}"
export PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-$PWD/.work/pycache}"
export PYTHONDONTWRITEBYTECODE="${PYTHONDONTWRITEBYTECODE:-1}"
export PYTHONPATH="${PYTHONPATH:-$PWD/src:$PWD}"
export HOLOCUE_ROOT="$PWD"
export HOLOCUE_SCENE_SET="${HOLOCUE_SCENE_SET:-reconstructed}"
case "$HOLOCUE_SCENE_SET" in
  legacy | reconstructed) ;;
  *)
    echo 'HOLOCUE_SCENE_SET must be legacy or reconstructed' >&2
    exit 2
    ;;
esac
export RUN_DIR="${RUN_DIR:-$PWD/runs/simulation/$HOLOCUE_SCENE_SET}"
mkdir -p "$TMPDIR" "$XDG_CACHE_HOME" "$PYTHONPYCACHEPREFIX" "$RUN_DIR"
APP_PYTHON="${APP_PYTHON:-$PWD/.venv-simulation/bin/python}"
test -x "$APP_PYTHON"
: "${BLENDER_BIN:?Set BLENDER_BIN to the installed Blender executable}"
test -x "$BLENDER_BIN"
"$APP_PYTHON" scripts/guard/resource_guard.py --rss-limit-gb 8 --log "$RUN_DIR/assets_resources.jsonl" --execute -- \
  "$APP_PYTHON" scripts/scenes/build_simulation_assets.py --scene-set "$HOLOCUE_SCENE_SET" --report "$RUN_DIR/assets.json"
"$APP_PYTHON" scripts/guard/resource_guard.py --rss-limit-gb 12 --log "$RUN_DIR/payload_resources.jsonl" --execute -- \
  "$APP_PYTHON" scripts/scenes/export_blender_payload.py --scene-set "$HOLOCUE_SCENE_SET"
for SCENE_FILE in "scenes/$HOLOCUE_SCENE_SET"/*/scene.json; do
  SCENE_DIR="$(dirname "$SCENE_FILE")"
  SCENE="$(basename "$SCENE_DIR")"
  "$APP_PYTHON" scripts/guard/resource_guard.py --rss-limit-gb 12 --log "$RUN_DIR/blender_${SCENE}_resources.jsonl" --execute -- \
    "$BLENDER_BIN" -b -t 4 --python-exit-code 1 --python scripts/scenes/build_blender_scene.py -- --scene "$SCENE" --scene-set "$HOLOCUE_SCENE_SET" --render
done
