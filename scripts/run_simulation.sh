#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
SERVICE="${1:?Specify api or viewer}"
shift
SERVICE_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --scene-set)
      export HOLOCUE_SCENE_SET="${2:?Specify legacy or reconstructed}"
      shift 2
      ;;
    --scene-set=*)
      export HOLOCUE_SCENE_SET="${1#*=}"
      shift
      ;;
    *)
      SERVICE_ARGS+=("$1")
      shift
      ;;
  esac
done
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
source scripts/guard/validate_runtime_paths.sh
mkdir -p "$TMPDIR" "$XDG_CACHE_HOME" "$PYTHONPYCACHEPREFIX" "$RUN_DIR"
APP_PYTHON="${APP_PYTHON:-$PWD/.venv-simulation/bin/python}"
test -x "$APP_PYTHON"
export HOLOCUE_MODE=live
case "$SERVICE" in
  api)
    exec "$APP_PYTHON" scripts/guard/resource_guard.py --rss-limit-gb 8 \
      --log "$RUN_DIR/api_resources.jsonl" --execute -- \
      "$APP_PYTHON" -m holocue.api --host 127.0.0.1 --port 8750 --scene-set "$HOLOCUE_SCENE_SET" "${SERVICE_ARGS[@]}"
    ;;
  viewer)
    exec "$APP_PYTHON" scripts/guard/resource_guard.py --rss-limit-gb 8 \
      --log "$RUN_DIR/viewer_resources.jsonl" --execute -- \
      "$APP_PYTHON" -m holocue.viewer --host 127.0.0.1 --port 8780 --scene-set "$HOLOCUE_SCENE_SET" "${SERVICE_ARGS[@]}"
    ;;
  *)
    echo 'Supported services are api and viewer' >&2
    exit 2
    ;;
esac
