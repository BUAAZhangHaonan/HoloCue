#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export TMPDIR="$PWD/.work/tmp"
export TMP="$TMPDIR"
export TEMP="$TMPDIR"
export XDG_CACHE_HOME="$PWD/.work/cache"
export PIP_CACHE_DIR="$PWD/.work/cache/pip"
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.work/browsers"
export PYTHONPYCACHEPREFIX="$PWD/.work/pycache"
export PYTHONPATH="$PWD/src:$PWD"
export HOLOCUE_ROOT="$PWD"
export HOLOCUE_MODE=live
mkdir -p "$TMPDIR" "$XDG_CACHE_HOME" "$PYTHONPYCACHEPREFIX" runs/simulation
APP_PYTHON="${APP_PYTHON:-$PWD/.venv-simulation/bin/python}"
test -x "$APP_PYTHON"
case "${1:?Specify api or viewer}" in
  api)
    exec "$APP_PYTHON" scripts/guard/resource_guard.py --rss-limit-gb 8 \
      --log "${RUN_DIR:-runs/simulation}/api_resources.jsonl" --execute -- \
      "$APP_PYTHON" -m holocue.api --host 127.0.0.1 --port 8750
    ;;
  viewer)
    exec "$APP_PYTHON" scripts/guard/resource_guard.py --rss-limit-gb 8 \
      --log "${RUN_DIR:-runs/simulation}/viewer_resources.jsonl" --execute -- \
      "$APP_PYTHON" -m holocue.viewer --host 127.0.0.1 --port 8780
    ;;
  *)
    echo 'Supported services are api and viewer' >&2
    exit 2
    ;;
esac
