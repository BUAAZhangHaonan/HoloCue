#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export HOLOCUE_ROOT="$PWD"
export HOLOCUE_MODE="${HOLOCUE_MODE:-live}"
exec .venv/bin/python scripts/guard/resource_guard.py --rss-limit-gb 8 --execute -- .venv/bin/python -m holocue.api
