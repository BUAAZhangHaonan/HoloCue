#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export HOLOCUE_ROOT="$PWD"
exec .venv/bin/python scripts/resource_guard.py --rss-limit-gb 8 --execute -- .venv/bin/python -m holocue.viewer
