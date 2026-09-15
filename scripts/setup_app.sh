#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python3}"
"$PYTHON" -c 'import sys; assert sys.version_info >= (3,11)'
[[ -d .venv ]] || "$PYTHON" -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
mkdir -p runs
.venv/bin/python -m pip freeze > runs/app_resolved_requirements.txt
